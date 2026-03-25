from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot import embeds
from bot.config import Config
from bot.utils.permissions import has_any_role


class MatchmakingCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg

    def _has_any_role(self, member: discord.Member, role_names: list) -> bool:
        return has_any_role(member.roles, role_names)

    def _is_owner(self, member: discord.Member) -> bool:
        return self._has_any_role(member, self.cfg.roles.get("owner", []))

    def _is_admin(self, member: discord.Member) -> bool:
        if self._is_owner(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("admin", []))

    def _can_buyer(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("buyer", []))

    def _can_seller(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("seller", []))

    def _blacklist_record(self, discord_id: str) -> Optional[dict]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            return db.is_blacklisted(conn, discord_id)
        finally:
            conn.close()

    async def _send_interaction_embed(
        self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = True
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    @commands.command(name="request")
    async def request_item(self, ctx: commands.Context, item_name: str, max_price: int) -> None:
        if not self._can_buyer(ctx.author):
            embed = embeds.permission_denied_embed("Buyer")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        if max_price <= 0:
            embed = embeds.invalid_usage_embed("!request \"item\" 25000")
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            request_id = db.create_request(conn, str(ctx.author.id), item_name, int(max_price))
            matches = db.find_matching_listings(conn, item_name, int(max_price))

            max_matches = 5
            created = 0
            for listing in matches:
                if db.is_blacklisted(conn, listing["seller_id"]):
                    continue
                if created >= max_matches:
                    break
                match_id = db.create_match(conn, request_id, listing["seller_id"])
                created += 1

                seller = ctx.guild.get_member(int(listing["seller_id"])) if ctx.guild else None
                if seller:
                    try:
                        await seller.send(
                            embed=embeds.match_alert_embed(match_id, item_name, max_price)
                        )
                    except discord.Forbidden:
                        pass

            if created == 0:
                db.update_request_status(conn, request_id, "NO_MATCH")
                db.log_audit(
                    conn,
                    actor_id=str(ctx.author.id),
                    action="REQUEST",
                    target_id=str(request_id),
                    details="no_match",
                )
                conn.commit()
                await ctx.send(embed=embeds.request_created_embed(request_id, item_name, max_price))
                await ctx.send(embed=embeds.no_sellers_embed(item_name))
                return

            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="REQUEST",
                target_id=str(request_id),
                details=f"matches={created}",
            )
            conn.commit()
        finally:
            conn.close()

        await ctx.send(embed=embeds.request_created_embed(request_id, item_name, max_price))

    @commands.command(name="cancel")
    async def cancel_request(self, ctx: commands.Context, request_id: int) -> None:
        if not self._can_buyer(ctx.author):
            embed = embeds.permission_denied_embed("Buyer")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            request = db.fetch_request(conn, int(request_id))
            if not request:
                embed = embeds.not_found_embed(str(request_id))
                await ctx.send(embed=embed)
                return

            if not self._is_admin(ctx.author) and request["buyer_id"] != str(ctx.author.id):
                embed = embeds.permission_denied_embed("Buyer")
                await ctx.send(embed=embed)
                return

            db.update_request_status(conn, int(request_id), "CANCELLED")
            db.close_matches_for_request(conn, int(request_id))
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="REQUEST_CANCEL",
                target_id=str(request_id),
                details="cancelled",
            )
            conn.commit()
        finally:
            conn.close()

        await ctx.send(embed=embeds.request_cancelled_embed(int(request_id)))

    @commands.command(name="accept")
    async def accept_match(self, ctx: commands.Context, match_id: int) -> None:
        if not self._can_seller(ctx.author):
            embed = embeds.permission_denied_embed("Seller")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            match = db.fetch_match(conn, int(match_id))
            if not match:
                embed = embeds.not_found_embed(str(match_id))
                await ctx.send(embed=embed)
                return

            if match["status"] != "PENDING":
                embed = embeds.match_closed_embed(int(match_id))
                await ctx.send(embed=embed)
                return

            if not self._is_admin(ctx.author) and match["seller_id"] != str(ctx.author.id):
                embed = embeds.permission_denied_embed("Seller")
                await ctx.send(embed=embed)
                return

            db.update_match_status(conn, int(match_id), "ACCEPTED")
            db.update_request_status(conn, int(match["request_id"]), "MATCHED")
            db.close_matches_for_request(conn, int(match["request_id"]), exclude_match_id=int(match_id))
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="MATCH_ACCEPT",
                target_id=str(match_id),
                details="accepted",
            )
            conn.commit()
        finally:
            conn.close()

        await ctx.send(embed=embeds.match_accepted_embed(int(match_id)))

    @commands.command(name="decline")
    async def decline_match(self, ctx: commands.Context, match_id: int) -> None:
        if not self._can_seller(ctx.author):
            embed = embeds.permission_denied_embed("Seller")
            await ctx.send(embed=embed)
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            embed = embeds.blacklisted_embed(author_blacklist.get("reason"))
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            match = db.fetch_match(conn, int(match_id))
            if not match:
                embed = embeds.not_found_embed(str(match_id))
                await ctx.send(embed=embed)
                return

            if match["status"] != "PENDING":
                embed = embeds.match_closed_embed(int(match_id))
                await ctx.send(embed=embed)
                return

            if not self._is_admin(ctx.author) and match["seller_id"] != str(ctx.author.id):
                embed = embeds.permission_denied_embed("Seller")
                await ctx.send(embed=embed)
                return

            db.update_match_status(conn, int(match_id), "DECLINED")
            remaining = db.list_matches_for_request(conn, int(match["request_id"]), status="PENDING")
            if not remaining:
                db.update_request_status(conn, int(match["request_id"]), "NO_MATCH")
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="MATCH_DECLINE",
                target_id=str(match_id),
                details="declined",
            )
            conn.commit()
        finally:
            conn.close()

        await ctx.send(embed=embeds.match_declined_embed(int(match_id)))

    @app_commands.command(name="request", description="Create a buyer request for the blackmarket.")
    @app_commands.describe(item_name="Item you want", max_price="Your max price")
    @app_commands.guild_only()
    async def request_slash(
        self, interaction: discord.Interaction, item_name: str, max_price: int
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Buyer"))
            return

        if not self._can_buyer(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Buyer"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        if max_price <= 0:
            await self._send_interaction_embed(
                interaction, embeds.invalid_usage_embed("/request item_name max_price")
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            request_id = db.create_request(conn, str(author.id), item_name, int(max_price))
            matches = db.find_matching_listings(conn, item_name, int(max_price))

            max_matches = 5
            created = 0
            for listing in matches:
                if db.is_blacklisted(conn, listing["seller_id"]):
                    continue
                if created >= max_matches:
                    break
                match_id = db.create_match(conn, request_id, listing["seller_id"])
                created += 1

                seller = interaction.guild.get_member(int(listing["seller_id"])) if interaction.guild else None
                if seller:
                    try:
                        await seller.send(embed=embeds.match_alert_embed(match_id, item_name, max_price))
                    except discord.Forbidden:
                        pass

            if created == 0:
                db.update_request_status(conn, request_id, "NO_MATCH")
                db.log_audit(
                    conn,
                    actor_id=str(author.id),
                    action="REQUEST",
                    target_id=str(request_id),
                    details="no_match",
                )
                conn.commit()
                await self._send_interaction_embed(
                    interaction, embeds.request_created_embed(request_id, item_name, max_price)
                )
                await interaction.followup.send(embed=embeds.no_sellers_embed(item_name), ephemeral=True)
                return

            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="REQUEST",
                target_id=str(request_id),
                details=f"matches={created}",
            )
            conn.commit()
        finally:
            conn.close()

        await self._send_interaction_embed(
            interaction, embeds.request_created_embed(request_id, item_name, max_price)
        )

    @app_commands.command(name="cancelrequest", description="Cancel one of your buyer requests.")
    @app_commands.describe(request_id="Request ID to cancel")
    @app_commands.guild_only()
    async def cancel_request_slash(self, interaction: discord.Interaction, request_id: int) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Buyer"))
            return

        if not self._can_buyer(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Buyer"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            request = db.fetch_request(conn, int(request_id))
            if not request:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(request_id)))
                return

            if not self._is_admin(author) and request["buyer_id"] != str(author.id):
                await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Buyer"))
                return

            db.update_request_status(conn, int(request_id), "CANCELLED")
            db.close_matches_for_request(conn, int(request_id))
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="REQUEST_CANCEL",
                target_id=str(request_id),
                details="cancelled",
            )
            conn.commit()
        finally:
            conn.close()

        await self._send_interaction_embed(interaction, embeds.request_cancelled_embed(int(request_id)))

    @app_commands.command(name="accept", description="Accept a pending seller match.")
    @app_commands.describe(match_id="Match ID to accept")
    @app_commands.guild_only()
    async def accept_slash(self, interaction: discord.Interaction, match_id: int) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Seller"))
            return

        if not self._can_seller(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Seller"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            match = db.fetch_match(conn, int(match_id))
            if not match:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(match_id)))
                return

            if match["status"] != "PENDING":
                await self._send_interaction_embed(interaction, embeds.match_closed_embed(int(match_id)))
                return

            if not self._is_admin(author) and match["seller_id"] != str(author.id):
                await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Seller"))
                return

            db.update_match_status(conn, int(match_id), "ACCEPTED")
            db.update_request_status(conn, int(match["request_id"]), "MATCHED")
            db.close_matches_for_request(conn, int(match["request_id"]), exclude_match_id=int(match_id))
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="MATCH_ACCEPT",
                target_id=str(match_id),
                details="accepted",
            )
            conn.commit()
        finally:
            conn.close()

        await self._send_interaction_embed(interaction, embeds.match_accepted_embed(int(match_id)))

    @app_commands.command(name="decline", description="Decline a pending seller match.")
    @app_commands.describe(match_id="Match ID to decline")
    @app_commands.guild_only()
    async def decline_slash(self, interaction: discord.Interaction, match_id: int) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Seller"))
            return

        if not self._can_seller(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Seller"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(
                interaction, embeds.blacklisted_embed(author_blacklist.get("reason"))
            )
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            match = db.fetch_match(conn, int(match_id))
            if not match:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(match_id)))
                return

            if match["status"] != "PENDING":
                await self._send_interaction_embed(interaction, embeds.match_closed_embed(int(match_id)))
                return

            if not self._is_admin(author) and match["seller_id"] != str(author.id):
                await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Seller"))
                return

            db.update_match_status(conn, int(match_id), "DECLINED")
            remaining = db.list_matches_for_request(conn, int(match["request_id"]), status="PENDING")
            if not remaining:
                db.update_request_status(conn, int(match["request_id"]), "NO_MATCH")
            db.log_audit(
                conn,
                actor_id=str(author.id),
                action="MATCH_DECLINE",
                target_id=str(match_id),
                details="declined",
            )
            conn.commit()
        finally:
            conn.close()

        await self._send_interaction_embed(interaction, embeds.match_declined_embed(int(match_id)))


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(MatchmakingCog(bot, cfg))
