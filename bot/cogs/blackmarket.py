import asyncio
from datetime import datetime, timedelta, timezone
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot import db
from bot import embeds
from bot.config import Config
from bot.utils.permissions import classify_member_access, has_any_role


class BlackmarketCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg
        self.post_cooldown_minutes = 10
        self.post_expiry_hours = 12
        self.bump_extension_hours = 6
        self.market_post_expiry_loop.start()

    def cog_unload(self) -> None:
        self.market_post_expiry_loop.cancel()

    def _has_any_role(self, member: discord.Member, role_names: list) -> bool:
        return has_any_role(member, role_names)

    def _is_owner(self, member: discord.Member) -> bool:
        return self._has_any_role(member, self.cfg.roles.get("owner", []))

    def _is_admin(self, member: discord.Member) -> bool:
        if self._is_owner(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("admin", []))

    def _verified_market_roles(self) -> list:
        return self.cfg.roles.get("verified_unlock", []) or self.cfg.roles.get("member", [])

    def _is_verified_member(self, member: discord.Member) -> bool:
        return self._has_any_role(member, self._verified_market_roles())

    def _can_blackmarket(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._is_verified_member(member)

    def _can_sell(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._is_verified_member(member) and self._has_any_role(member, self.cfg.roles.get("seller", []))

    def _can_buy(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._is_verified_member(member) and self._has_any_role(member, self.cfg.roles.get("buyer", []))

    def _trusted_roles(self, member: discord.Member) -> list[str]:
        access_level, matched_roles = classify_member_access(member, self.cfg.roles)
        if access_level != "trusted":
            return []
        return matched_roles

    def _expiry_iso(self, hours: int) -> str:
        return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")

    def _remaining_cooldown_minutes(self, created_at: Optional[str]) -> int:
        if not created_at:
            return 0
        try:
            created = datetime.fromisoformat(created_at)
        except ValueError:
            return 0
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        unlock_at = created + timedelta(minutes=self.post_cooldown_minutes)
        remaining = unlock_at - datetime.now(timezone.utc)
        return max(0, int(remaining.total_seconds() // 60) + (1 if remaining.total_seconds() > 0 else 0))

    async def _resolve_text_channel(self, channel_id: Optional[int]) -> Optional[discord.TextChannel]:
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                return None
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def _market_target_channels(
        self,
        interaction: discord.Interaction,
        *,
        action: str,
        asset_type: str,
        trusted_roles: list[str],
    ) -> list[discord.TextChannel]:
        target_ids: list[Optional[int]] = []
        normalized_asset = (asset_type or "gold").strip().casefold()
        if action == "buy":
            if normalized_asset == "item":
                target_ids.append(self.cfg.looking_for_items_channel_id or self.cfg.market_channel_id)
            else:
                target_ids.append(self.cfg.looking_for_gold_channel_id or self.cfg.market_channel_id)
        else:
            target_ids.append(self.cfg.market_channel_id)
        if trusted_roles:
            target_ids.append(self.cfg.trusted_market_channel_id)

        channels: list[discord.TextChannel] = []
        seen: set[int] = set()
        for channel_id in target_ids:
            channel = await self._resolve_text_channel(channel_id)
            if channel is None or channel.id in seen:
                continue
            channels.append(channel)
            seen.add(channel.id)
        return channels

    async def _gold_target_channels(
        self,
        *,
        action: str,
        trusted_roles: list[str],
    ) -> tuple[list[discord.TextChannel], list[discord.TextChannel]]:
        primary_ids: list[Optional[int]] = []
        delayed_ids: list[Optional[int]] = []
        if action == "buy":
            primary_ids.append(self.cfg.looking_for_gold_channel_id)
        else:
            primary_ids.append(self.cfg.market_channel_id)
            if trusted_roles:
                delayed_ids.append(self.cfg.trusted_market_channel_id)

        async def resolve(ids: list[Optional[int]]) -> list[discord.TextChannel]:
            channels: list[discord.TextChannel] = []
            seen: set[int] = set()
            for channel_id in ids:
                channel = await self._resolve_text_channel(channel_id)
                if channel is None or channel.id in seen:
                    continue
                channels.append(channel)
                seen.add(channel.id)
            return channels

        return await resolve(primary_ids), await resolve(delayed_ids)

    def _lane_label(self, action: str, asset_type: str) -> str:
        normalized_asset = (asset_type or "gold").strip().casefold()
        if action == "buy":
            return "looking for items" if normalized_asset == "item" else "looking for gold"
        return "market"

    async def _single_target_channel(
        self,
        channel_id: Optional[int],
    ) -> Optional[discord.TextChannel]:
        return await self._resolve_text_channel(channel_id)

    async def _post_saved_market_embed(self, post: dict, channel: discord.TextChannel) -> Optional[discord.Message]:
        trusted_roles = ["trusted boost"] if post.get("trusted_boost") else None
        embed = embeds.market_trade_post_embed(
            asset_type=str(post["asset_type"]),
            action=str(post["action"]),
            user_mention=f"<@{post['discord_id']}>",
            item_name=str(post["item_name"]),
            price=int(post["price"]),
            details=str(post["details"]),
            trusted_roles=trusted_roles,
            duplicate_count=1,
        )
        try:
            return await channel.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            return None

    async def _maybe_market_matches(
        self,
        *,
        discord_id: str,
        asset_type: str,
        action: str,
        item_name: str,
        price: int,
    ) -> int:
        opposite = "buy" if action == "sell" else "sell"
        conn = db.get_connection(self.cfg.db_path)
        try:
            matches = db.find_market_matches(
                conn,
                asset_type=asset_type,
                opposite_action=opposite,
                item_name=item_name,
                price=price,
                exclude_discord_id=discord_id,
                limit=5,
            )
            return len(matches)
        finally:
            conn.close()

    def _blacklist_record(self, discord_id: str) -> Optional[dict]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            return db.is_blacklisted(conn, discord_id)
        finally:
            conn.close()

    def _extract_first_discord_id(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        match = re.search(r"<@!?(\d+)>", text)
        if match:
            return match.group(1)
        digits = re.sub(r"\D", "", text)
        return digits or None

    def _vouch_payload_from_message(self, message: discord.Message) -> Optional[dict]:
        subject_discord_id: Optional[str] = None
        details_value = ""

        for embed in message.embeds:
            for field in embed.fields:
                field_name = (field.name or "").strip().upper()
                if field_name == "[USER]" and not subject_discord_id:
                    subject_discord_id = self._extract_first_discord_id(field.value)
                if field_name == "[DETAILS]" and not details_value:
                    details_value = (field.value or "").strip()

        if not subject_discord_id and message.mentions:
            subject_discord_id = str(message.mentions[0].id)
        if not subject_discord_id and not message.author.bot:
            subject_discord_id = str(message.author.id)
        if not subject_discord_id:
            return None

        content_value = (message.content or "").strip()
        attachment_urls = [attachment.url for attachment in message.attachments[:3] if attachment.url]
        if not details_value:
            details_value = content_value
        if attachment_urls:
            attachment_note = "Attachments: " + ", ".join(attachment_urls)
            details_value = f"{details_value}\n{attachment_note}".strip() if details_value else attachment_note
        if not details_value:
            return None

        voucher_discord_id = None if message.author.bot else str(message.author.id)
        if not voucher_discord_id:
            voucher_discord_id = subject_discord_id

        return {
            "source_message_id": str(message.id),
            "guild_id": str(message.guild.id) if message.guild else None,
            "channel_id": str(message.channel.id),
            "subject_discord_id": subject_discord_id,
            "voucher_discord_id": voucher_discord_id,
            "details": details_value[:2000],
            "source_url": message.jump_url,
            "created_at": message.created_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
        }

    async def _import_vouches_from_channel(
        self,
        channel: discord.TextChannel,
        *,
        limit: int,
    ) -> tuple[int, int, int, int]:
        scanned = 0
        inserted = 0
        updated = 0
        skipped = 0
        payloads: list[dict] = []

        async for message in channel.history(limit=limit, oldest_first=True):
            scanned += 1
            payload = self._vouch_payload_from_message(message)
            if payload is None:
                skipped += 1
                continue
            payloads.append(payload)

        conn = db.get_connection(self.cfg.db_path)
        try:
            for payload in payloads:
                result = db.upsert_vouch(conn, **payload)
                if result == "inserted":
                    inserted += 1
                else:
                    updated += 1
            conn.commit()
        finally:
            conn.close()

        return scanned, inserted, updated, skipped

    async def _send_interaction_embed(
        self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = True
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    async def _send_market_list_interaction(
        self,
        interaction: discord.Interaction,
        *,
        query: Optional[str] = None,
        ephemeral: bool = True,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Blackmarket"), ephemeral=ephemeral)
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction,
                embeds.blacklisted_embed(author_blacklist.get("reason")),
                ephemeral=ephemeral,
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listings = db.list_listings(conn, item_query=query if query else None)
        finally:
            conn.close()

        await self._send_interaction_embed(interaction, embeds.listings_embed(listings), ephemeral=ephemeral)

    async def handle_market_list_menu_button(self, interaction: discord.Interaction) -> None:
        await self._send_market_list_interaction(interaction, ephemeral=True)

    async def handle_repost_latest_market_post(
        self,
        interaction: discord.Interaction,
        *,
        asset_type: Optional[str] = None,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return
        conn = db.get_connection(self.cfg.db_path)
        try:
            post = db.fetch_latest_market_post(
                conn,
                discord_id=str(author.id),
                asset_type=asset_type,
                statuses=["OPEN", "BUMPED", "EXPIRED"],
            )
        finally:
            conn.close()
        if not post:
            await self._send_interaction_embed(interaction, embeds.not_found_embed("saved market post"))
            return
        channel = await self._resolve_text_channel(int(post["channel_id"]))
        if channel is None:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("The saved post channel is no longer available."))
            return
        posted_message = await self._post_saved_market_embed(post, channel)
        if posted_message is None:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            db.create_market_post(
                conn,
                discord_id=str(author.id),
                guild_id=str(post.get("guild_id") or interaction.guild_id or ""),
                channel_id=str(channel.id),
                action=str(post["action"]),
                asset_type=str(post["asset_type"]),
                item_name=str(post["item_name"]),
                price=int(post["price"]),
                details=str(post["details"]),
                trusted_boost=bool(post.get("trusted_boost")),
                source_post_id=str(posted_message.id),
                expires_at=self._expiry_iso(self.post_expiry_hours),
            )
            conn.commit()
        finally:
            conn.close()
        await self._send_interaction_embed(interaction, embeds.make_embed(embeds.TITLE_BLACKMARKET, "Saved post reposted cleanly.", embeds.COLOR_OK), ephemeral=True)

    async def handle_bump_latest_market_post(
        self,
        interaction: discord.Interaction,
        *,
        asset_type: Optional[str] = None,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return
        conn = db.get_connection(self.cfg.db_path)
        try:
            post = db.fetch_latest_market_post(
                conn,
                discord_id=str(author.id),
                asset_type=asset_type,
                statuses=["OPEN", "BUMPED"],
            )
        finally:
            conn.close()
        if not post:
            await self._send_interaction_embed(interaction, embeds.not_found_embed("active market post"))
            return
        channel = await self._resolve_text_channel(int(post["channel_id"]))
        if channel is None:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("The active post channel is no longer available."))
            return
        posted_message = await self._post_saved_market_embed(post, channel)
        if posted_message is None:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return
        conn = db.get_connection(self.cfg.db_path)
        try:
            db.bump_market_post(conn, int(post["id"]), expires_at=self._expiry_iso(self.bump_extension_hours))
            conn.commit()
        finally:
            conn.close()
        await self._send_interaction_embed(interaction, embeds.make_embed(embeds.TITLE_BLACKMARKET, "Active post bumped.", embeds.COLOR_OK), ephemeral=True)

    async def handle_remove_latest_market_post(
        self,
        interaction: discord.Interaction,
        *,
        asset_type: Optional[str] = None,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        embed = await self._remove_latest_market_post_for_member(author, asset_type=asset_type)
        await self._send_interaction_embed(interaction, embed, ephemeral=True)

    async def _create_listing_for_member(
        self,
        member: discord.Member,
        item_name: str,
        price: int,
    ) -> discord.Embed:
        conn = db.get_connection(self.cfg.db_path)
        try:
            listing_id = db.create_listing(conn, str(member.id), item_name, int(price))
            db.log_audit(
                conn,
                actor_id=str(member.id),
                action="LISTING_ADD",
                target_id=str(listing_id),
                details=f"item={item_name}|price={price}",
            )
            conn.commit()
        finally:
            conn.close()
        return embeds.listing_created_embed(listing_id, item_name, price)

    async def _remove_listing_for_member(
        self,
        member: discord.Member,
        listing_id: int,
    ) -> discord.Embed:
        conn = db.get_connection(self.cfg.db_path)
        try:
            listing = db.fetch_listing(conn, int(listing_id))
            if not listing:
                return embeds.not_found_embed(str(listing_id))

            if not self._is_admin(member) and listing["seller_id"] != str(member.id):
                return embeds.permission_denied_embed("Verified Member")

            db.close_listing(conn, int(listing_id))
            db.log_audit(
                conn,
                actor_id=str(member.id),
                action="LISTING_REMOVE",
                target_id=str(listing_id),
                details="removed",
            )
            conn.commit()
        finally:
            conn.close()
        return embeds.listing_removed_embed(int(listing_id))

    async def _delete_market_post_message(self, post: dict) -> bool:
        source_post_id = post.get("source_post_id")
        channel_id = post.get("channel_id")
        if not source_post_id or not channel_id:
            return False
        channel = await self._resolve_text_channel(int(channel_id))
        if channel is None:
            return False
        try:
            await channel.get_partial_message(int(source_post_id)).delete()
            return True
        except (ValueError, discord.HTTPException, discord.Forbidden, discord.NotFound):
            return False

    async def _remove_latest_market_post_for_member(
        self,
        member: discord.Member,
        *,
        asset_type: Optional[str] = None,
    ) -> discord.Embed:
        conn = db.get_connection(self.cfg.db_path)
        try:
            post = db.fetch_latest_market_post(
                conn,
                discord_id=str(member.id),
                asset_type=asset_type,
                statuses=["OPEN", "BUMPED"],
            )
            if not post:
                return embeds.not_found_embed("active market post")
            related_posts = db.list_market_posts_by_signature(
                conn,
                discord_id=str(member.id),
                asset_type=str(post["asset_type"]),
                action=str(post["action"]),
                item_name=str(post["item_name"]),
                price=int(post["price"]),
                details=str(post["details"]),
                statuses=["OPEN", "BUMPED"],
                limit=10,
            )
        finally:
            conn.close()

        deleted_count = 0
        for related_post in related_posts:
            if await self._delete_market_post_message(related_post):
                deleted_count += 1

        post_ids = [int(related_post["id"]) for related_post in related_posts] or [int(post["id"])]
        conn = db.get_connection(self.cfg.db_path)
        try:
            for post_id in post_ids:
                db.close_market_post(conn, post_id, status="REMOVED")
            db.log_audit(
                conn,
                actor_id=str(member.id),
                action="MARKET_POST_REMOVE",
                target_id=",".join(str(post_id) for post_id in post_ids),
                details=f"asset={post['asset_type']}|action={post['action']}|messages_deleted={deleted_count}",
            )
            conn.commit()
        finally:
            conn.close()

        return embeds.market_trade_removed_embed(
            asset_type=str(post["asset_type"]),
            action=str(post["action"]),
            post_count=len(post_ids),
            deleted_count=deleted_count,
        )

    async def handle_market_add_modal(
        self,
        interaction: discord.Interaction,
        item_name: str,
        price_text: str,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        cleaned_name = (item_name or "").strip()
        try:
            price = int((price_text or "").strip())
        except ValueError:
            price = 0

        if not cleaned_name or price <= 0:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("item name + positive price"))
            return

        embed = await self._create_listing_for_member(author, cleaned_name, price)
        await self._send_interaction_embed(interaction, embed, ephemeral=True)

    async def handle_market_remove_modal(
        self,
        interaction: discord.Interaction,
        listing_id_text: str,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        try:
            listing_id = int((listing_id_text or "").strip())
        except ValueError:
            listing_id = 0

        if listing_id <= 0:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("listing ID"))
            return

        embed = await self._remove_listing_for_member(author, listing_id)
        await self._send_interaction_embed(interaction, embed, ephemeral=True)

    async def _handle_routed_trade_modal(
        self,
        interaction: discord.Interaction,
        *,
        asset_type: str,
        action: str,
        item_name: str,
        price_text: str,
        details: str,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Trusted Seller or Buyer"))
            return

        normalized_action = "sell" if (action or "").strip().casefold() == "sell" else "buy"
        normalized_asset = "item" if (asset_type or "").strip().casefold() == "item" else "gold"
        allowed = self._can_sell(author) if normalized_action == "sell" else self._can_buy(author)
        required_role = "Seller" if normalized_action == "sell" else "Buyer"
        if not allowed:
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed(required_role))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        cleaned_name = (item_name or "").strip()
        cleaned_details = (details or "").strip()
        try:
            price = int((price_text or "").strip())
        except ValueError:
            price = 0

        if not cleaned_name or not cleaned_details or price <= 0:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed(f"item + positive {normalized_asset} price + short details"),
            )
            return

        trusted_roles = self._trusted_roles(author)
        conn = db.get_connection(self.cfg.db_path)
        try:
            cooldown = db.find_market_post_cooldown(
                conn,
                discord_id=str(author.id),
                asset_type=normalized_asset,
                action=normalized_action,
            )
        finally:
            conn.close()
        if cooldown:
            minutes_left = self._remaining_cooldown_minutes(cooldown.get("created_at"))
            if minutes_left > 0:
                await self._send_interaction_embed(
                    interaction,
                    embeds.market_cooldown_embed(minutes_left, self._lane_label(normalized_action, normalized_asset)),
                )
                return

        target_channels = await self._market_target_channels(
            interaction,
            action=normalized_action,
            asset_type=normalized_asset,
            trusted_roles=trusted_roles,
        )
        if not target_channels:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed(f"Set the market lane channel IDs before posting {normalized_asset}."),
            )
            return

        duplicate_count = len(target_channels)
        post_embed = embeds.market_trade_post_embed(
            asset_type=normalized_asset,
            action=normalized_action,
            user_mention=author.mention,
            item_name=cleaned_name,
            price=price,
            details=cleaned_details,
            trusted_roles=trusted_roles,
            duplicate_count=duplicate_count,
        )
        expires_at = self._expiry_iso(self.post_expiry_hours)
        conn = db.get_connection(self.cfg.db_path)
        created_post_ids: list[int] = []
        try:
            for channel in target_channels:
                posted_message = await channel.send(embed=post_embed)
                post_id = db.create_market_post(
                    conn,
                    discord_id=str(author.id),
                    guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                    channel_id=str(channel.id),
                    action=normalized_action,
                    asset_type=normalized_asset,
                    item_name=cleaned_name,
                    price=price,
                    details=cleaned_details,
                    trusted_boost=bool(trusted_roles),
                    source_post_id=str(posted_message.id),
                    expires_at=expires_at,
                )
                created_post_ids.append(post_id)
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="MARKET_POST_ADD",
                target_id=",".join(str(post_id) for post_id in created_post_ids),
                details=f"asset={normalized_asset}|action={normalized_action}|channels={','.join(str(channel.id) for channel in target_channels)}",
            )
            conn.commit()
        finally:
            conn.close()

        match_count = await self._maybe_market_matches(
            discord_id=str(author.id),
            asset_type=normalized_asset,
            action=normalized_action,
            item_name=cleaned_name,
            price=price,
        )

        await self._send_interaction_embed(
            interaction,
            embeds.market_trade_posted_embed(
                asset_type=normalized_asset,
                action=normalized_action,
                item_name=cleaned_name,
                price=price,
                duplicate_count=duplicate_count,
                trusted_roles=trusted_roles,
            ),
            ephemeral=True,
        )
        if match_count:
            await interaction.followup.send(
                embed=embeds.market_match_beta_embed(match_count, asset_type=normalized_asset),
                ephemeral=True,
            )

    async def handle_gold_trade_modal(
        self,
        interaction: discord.Interaction,
        *,
        action: str,
        amount: str,
        rate_or_price: str,
        payment_type: str,
        transfer_type: str,
        notes: str,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Trusted Seller or Buyer"))
            return

        normalized_action = "sell" if (action or "").strip().casefold() == "sell" else "buy"
        allowed = self._can_sell(author) if normalized_action == "sell" else self._can_buy(author)
        required_role = "Seller" if normalized_action == "sell" else "Buyer"
        if not allowed:
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed(required_role))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        cleaned_amount = (amount or "").strip()
        cleaned_rate = (rate_or_price or "").strip()
        cleaned_payment = (payment_type or "").strip()
        cleaned_transfer = (transfer_type or "").strip()
        cleaned_notes = (notes or "").strip()
        if not all((cleaned_amount, cleaned_rate, cleaned_payment, cleaned_transfer, cleaned_notes)):
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("amount + rate/price + payment type + transfer type + notes"),
            )
            return

        digits = re.findall(r"\d+", cleaned_rate.replace(",", ""))
        price = int(digits[0]) if digits else 0
        if price <= 0:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("rate / price needs at least one usable number"),
            )
            return

        trusted_roles = self._trusted_roles(author)
        conn = db.get_connection(self.cfg.db_path)
        try:
            cooldown = db.find_market_post_cooldown(
                conn,
                discord_id=str(author.id),
                asset_type="gold",
                action=normalized_action,
            )
        finally:
            conn.close()
        if cooldown:
            minutes_left = self._remaining_cooldown_minutes(cooldown.get("created_at"))
            if minutes_left > 0:
                await self._send_interaction_embed(
                    interaction,
                    embeds.market_cooldown_embed(minutes_left, self._lane_label(normalized_action, "gold")),
                )
                return

        target_channels, delayed_channels = await self._gold_target_channels(
            action=normalized_action,
            trusted_roles=trusted_roles,
        )
        if not target_channels:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("Set the gold market lane channel IDs before posting gold."),
            )
            return

        gold_details = (
            f"Amount: {cleaned_amount}\n"
            f"Rate / Price: {cleaned_rate}\n"
            f"Payment Type: {cleaned_payment}\n"
            f"Transfer Type: {cleaned_transfer}\n"
            f"Notes: {cleaned_notes}"
        )
        duplicate_count = len(target_channels)
        post_embed = embeds.market_trade_post_embed(
            asset_type="gold",
            action=normalized_action,
            user_mention=author.mention,
            item_name=cleaned_amount,
            price=price,
            details=gold_details,
            trusted_roles=trusted_roles,
            duplicate_count=duplicate_count,
        )
        post_embed.set_field_at(1, name="[AMOUNT]", value=cleaned_amount, inline=True)
        post_embed.set_field_at(2, name="[RATE / PRICE]", value=cleaned_rate, inline=True)

        expires_at = self._expiry_iso(self.post_expiry_hours)
        conn = db.get_connection(self.cfg.db_path)
        created_post_ids: list[int] = []
        try:
            for channel in target_channels:
                posted_message = await channel.send(embed=post_embed)
                post_id = db.create_market_post(
                    conn,
                    discord_id=str(author.id),
                    guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                    channel_id=str(channel.id),
                    action=normalized_action,
                    asset_type="gold",
                    item_name=cleaned_amount,
                    price=price,
                    details=gold_details,
                    trusted_boost=bool(trusted_roles),
                    source_post_id=str(posted_message.id),
                    expires_at=expires_at,
                )
                created_post_ids.append(post_id)
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="MARKET_POST_ADD",
                target_id=",".join(str(post_id) for post_id in created_post_ids),
                details=f"asset=gold|action={normalized_action}|channels={','.join(str(channel.id) for channel in target_channels)}",
            )
            conn.commit()
        finally:
            conn.close()

        if delayed_channels and normalized_action == "sell":
            await asyncio.sleep(2)
            for delayed_channel in delayed_channels:
                delayed_message = await delayed_channel.send(embed=post_embed)
                conn = db.get_connection(self.cfg.db_path)
                try:
                    db.create_market_post(
                        conn,
                        discord_id=str(author.id),
                        guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                        channel_id=str(delayed_channel.id),
                        action=normalized_action,
                        asset_type="gold",
                        item_name=cleaned_amount,
                        price=price,
                        details=gold_details,
                        trusted_boost=True,
                        source_post_id=str(delayed_message.id),
                        expires_at=expires_at,
                    )
                    conn.commit()
                finally:
                    conn.close()

        match_count = await self._maybe_market_matches(
            discord_id=str(author.id),
            asset_type="gold",
            action=normalized_action,
            item_name=cleaned_amount,
            price=price,
        )

        await self._send_interaction_embed(
            interaction,
            embeds.market_trade_posted_embed(
                asset_type="gold",
                action=normalized_action,
                item_name=cleaned_amount,
                price=price,
                duplicate_count=duplicate_count,
                trusted_roles=trusted_roles,
            ),
            ephemeral=True,
        )
        if match_count:
            await interaction.followup.send(
                embed=embeds.market_match_beta_embed(match_count, asset_type="gold"),
                ephemeral=True,
            )

    async def handle_item_trade_modal(
        self,
        interaction: discord.Interaction,
        *,
        action: str,
        item_name: str,
        price_text: str,
        details: str,
    ) -> None:
        await self._handle_routed_trade_modal(
            interaction,
            asset_type="item",
            action=action,
            item_name=item_name,
            price_text=price_text,
            details=details,
        )

    async def handle_price_check_modal(
        self,
        interaction: discord.Interaction,
        *,
        item_name: str,
        details: str,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        cleaned_name = (item_name or "").strip()
        cleaned_details = (details or "").strip()
        if not cleaned_name or not cleaned_details:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("item + short price check details"))
            return

        channel = await self._single_target_channel(self.cfg.price_checks_channel_id)
        if channel is None:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("Set the price checks channel ID before posting."))
            return

        await channel.send(embed=embeds.price_check_post_embed(user_mention=author.mention, item_name=cleaned_name, details=cleaned_details))
        await self._send_interaction_embed(
            interaction,
            embeds.price_check_posted_embed(cleaned_name, channel.mention),
            ephemeral=True,
        )

    async def handle_proof_of_sale_modal(
        self,
        interaction: discord.Interaction,
        *,
        details: str,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        cleaned_details = (details or "").strip()
        if not cleaned_details:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("short proof or vouch details"))
            return

        channel = await self._single_target_channel(self.cfg.proof_of_selling_channel_id)
        if channel is None:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("Set the proof of selling channel ID before posting."))
            return

        posted_message = await channel.send(
            embed=embeds.proof_of_sale_post_embed(user_mention=author.mention, details=cleaned_details)
        )
        payload = self._vouch_payload_from_message(posted_message)
        if payload is not None:
            conn = db.get_connection(self.cfg.db_path)
            try:
                db.upsert_vouch(conn, **payload)
                conn.commit()
            finally:
                conn.close()
        await self._send_interaction_embed(
            interaction,
            embeds.proof_of_sale_posted_embed(channel.mention),
            ephemeral=True,
        )

    @tasks.loop(minutes=5)
    async def market_post_expiry_loop(self) -> None:
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = db.get_connection(self.cfg.db_path)
        try:
            posts = db.list_expired_market_posts(conn, now_iso, limit=25)
        finally:
            conn.close()

        for post in posts:
            await self._process_expired_market_post(post)

    async def _process_expired_market_post(self, post: dict) -> None:
        conn = db.get_connection(self.cfg.db_path)
        try:
            if post.get("trusted_boost") and int(post.get("bump_count") or 0) < 1:
                channel = await self._resolve_text_channel(int(post["channel_id"]))
                if channel is not None:
                    guild = channel.guild
                    member = guild.get_member(int(post["discord_id"])) if guild else None
                    mention = member.mention if member else f"<@{post['discord_id']}>"
                    embed = embeds.market_trade_post_embed(
                        asset_type=str(post["asset_type"]),
                        action=str(post["action"]),
                        user_mention=mention,
                        item_name=str(post["item_name"]),
                        price=int(post["price"]),
                        details=str(post["details"]),
                        trusted_roles=["trusted boost"],
                        duplicate_count=1,
                    )
                    await channel.send(embed=embed)
                db.bump_market_post(conn, int(post["id"]), expires_at=self._expiry_iso(self.bump_extension_hours))
            else:
                db.close_market_post(conn, int(post["id"]), status="EXPIRED")
            conn.commit()
        finally:
            conn.close()

    @market_post_expiry_loop.before_loop
    async def before_market_post_expiry_loop(self) -> None:
        await self.bot.wait_until_ready()

    @commands.group(name="blackmarket", invoke_without_command=True)
    async def blackmarket(self, ctx: commands.Context) -> None:
        embed = embeds.invalid_usage_embed("!blackmarket list | add | remove")
        await ctx.send(embed=embed)

    @blackmarket.command(name="list")
    async def list_listings(self, ctx: commands.Context, *, query: str = "") -> None:
        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            listings = db.list_listings(conn, item_query=query if query else None)
        finally:
            conn.close()

        embed = embeds.listings_embed(listings)
        await ctx.send(embed=embed)

    @blackmarket.command(name="add")
    async def add_listing(self, ctx: commands.Context, item_name: str, price: int) -> None:
        if not self._can_blackmarket(ctx.author):
            embed = embeds.permission_denied_embed("Verified Member")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        if price <= 0:
            embed = embeds.invalid_usage_embed("!blackmarket add \"item\" 25000")
            await ctx.send(embed=embed)
            return

        embed = await self._create_listing_for_member(ctx.author, item_name, int(price))
        await ctx.send(embed=embed)

    @blackmarket.command(name="remove")
    async def remove_listing(self, ctx: commands.Context, listing_id: int) -> None:
        if not self._can_blackmarket(ctx.author):
            embed = embeds.permission_denied_embed("Verified Member")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        embed = await self._remove_listing_for_member(ctx.author, int(listing_id))
        await ctx.send(embed=embed)

    @commands.command(name="vouches")
    async def vouches_command(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        target = member or ctx.author
        conn = db.get_connection(self.cfg.db_path)
        try:
            total_count = db.count_vouches_for_member(conn, str(target.id))
            rows = db.list_vouches_for_member(conn, subject_discord_id=str(target.id), limit=5)
        finally:
            conn.close()
        await ctx.send(
            embed=embeds.vouch_lookup_embed(
                member_mention=target.mention,
                total_count=total_count,
                rows=rows,
            )
        )

    @commands.command(name="syncvouches")
    async def sync_vouches_command(self, ctx: commands.Context, lookback: Optional[int] = 300) -> None:
        if not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Victor Admin"))
            return

        lookback_value = int(lookback or 300)
        if lookback_value < 1 or lookback_value > 2000:
            await ctx.send(embed=embeds.invalid_usage_embed("!syncvouches [lookback between 1 and 2000]"))
            return

        channel = await self._single_target_channel(self.cfg.proof_of_selling_channel_id)
        if channel is None:
            await ctx.send(embed=embeds.invalid_usage_embed("Set the proof of selling channel ID before syncing vouches."))
            return

        scanned, inserted, updated, skipped = await self._import_vouches_from_channel(channel, limit=lookback_value)
        conn = db.get_connection(self.cfg.db_path)
        try:
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="VOUCH_IMPORT",
                target_id=str(channel.id),
                details=f"scanned={scanned}|inserted={inserted}|updated={updated}|skipped={skipped}",
            )
            conn.commit()
        finally:
            conn.close()
        await ctx.send(
            embed=embeds.vouch_import_summary_embed(
                channel_mention=channel.mention,
                scanned=scanned,
                inserted=inserted,
                updated=updated,
                skipped=skipped,
            )
        )

    @app_commands.command(name="marketlist", description="Show open blackmarket listings.")
    @app_commands.describe(query="Optional item name filter")
    @app_commands.guild_only()
    async def market_list_slash(
        self, interaction: discord.Interaction, query: Optional[str] = None
    ) -> None:
        await self._send_market_list_interaction(interaction, query=query, ephemeral=True)

    @app_commands.command(name="marketadd", description="Create a blackmarket listing.")
    @app_commands.describe(item_name="Item to list", price="Listing price")
    @app_commands.guild_only()
    async def market_add_slash(
        self, interaction: discord.Interaction, item_name: str, price: int
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        if price <= 0:
            await self._send_interaction_embed(
                interaction, embeds.invalid_usage_embed("/marketadd item_name price")
            )
            return

        embed = await self._create_listing_for_member(author, item_name, int(price))
        await self._send_interaction_embed(interaction, embed)

    @app_commands.command(name="marketremove", description="Remove one of your blackmarket listings.")
    @app_commands.describe(listing_id="Listing ID to remove")
    @app_commands.guild_only()
    async def market_remove_slash(self, interaction: discord.Interaction, listing_id: int) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        if not self._can_blackmarket(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verified Member"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        embed = await self._remove_listing_for_member(author, int(listing_id))
        await self._send_interaction_embed(interaction, embed)

    @app_commands.command(name="vouches", description="Show recent vouches for a member.")
    @app_commands.describe(member="Member to inspect")
    @app_commands.guild_only()
    async def vouches_slash(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
    ) -> None:
        author = interaction.user
        target = member if isinstance(member, discord.Member) else author if isinstance(author, discord.Member) else None
        if target is None:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("/vouches member"))
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            total_count = db.count_vouches_for_member(conn, str(target.id))
            rows = db.list_vouches_for_member(conn, subject_discord_id=str(target.id), limit=5)
        finally:
            conn.close()
        await self._send_interaction_embed(
            interaction,
            embeds.vouch_lookup_embed(
                member_mention=target.mention,
                total_count=total_count,
                rows=rows,
            ),
            ephemeral=False,
        )

    @app_commands.command(name="syncvouches", description="Import vouches from the proof channel into Victor's index.")
    @app_commands.describe(lookback="How many recent proof-channel messages to scan")
    @app_commands.guild_only()
    async def sync_vouches_slash(
        self,
        interaction: discord.Interaction,
        lookback: app_commands.Range[int, 1, 2000] = 300,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return

        channel = await self._single_target_channel(self.cfg.proof_of_selling_channel_id)
        if channel is None:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("Set the proof of selling channel ID before syncing vouches."),
            )
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        scanned, inserted, updated, skipped = await self._import_vouches_from_channel(channel, limit=lookback)
        conn = db.get_connection(self.cfg.db_path)
        try:
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="VOUCH_IMPORT",
                target_id=str(channel.id),
                details=f"scanned={scanned}|inserted={inserted}|updated={updated}|skipped={skipped}",
            )
            conn.commit()
        finally:
            conn.close()
        await self._send_interaction_embed(
            interaction,
            embeds.vouch_import_summary_embed(
                channel_mention=channel.mention,
                scanned=scanned,
                inserted=inserted,
                updated=updated,
                skipped=skipped,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(BlackmarketCog(bot, cfg))
