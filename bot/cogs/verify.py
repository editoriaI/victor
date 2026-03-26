import logging
import secrets
import string
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot import embeds
from bot.config import Config
from bot.highrise_api import HighriseApiClient, HighriseApiError, HighriseProfile, HighriseUserNotFound
from bot.cogs.staff_console import send_verify_review_post
from bot.utils.permissions import has_any_role, normalize_role_name

VERIFY_CONFIRM_BUTTON_ID = "victor:verify_confirm"


class VerifyConfirmView(discord.ui.View):
    def __init__(self, cog: "VerifyCog") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Recheck Bio",
        style=discord.ButtonStyle.success,
        emoji="🕯️",
        custom_id=VERIFY_CONFIRM_BUTTON_ID,
    )
    async def confirm_bio_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.handle_verify_confirm_button(interaction)


class VerifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg
        self.logger = logging.getLogger("victor.verify")

    def _has_any_role(self, member: discord.Member, role_names: List[str]) -> bool:
        return has_any_role(member.roles, role_names)

    def _is_owner(self, member: discord.Member) -> bool:
        return self._has_any_role(member, self.cfg.roles.get("owner", []))

    def _is_admin(self, member: discord.Member) -> bool:
        if self._is_owner(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("admin", []))

    def _can_verify(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("verifier", []))

    def _can_view_others(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("verifier", []))

    def _blacklist_record(self, discord_id: str) -> Optional[dict]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            return db.is_blacklisted(conn, discord_id)
        finally:
            conn.close()

    async def _send_interaction_embed(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
        ephemeral: bool = True,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        kwargs = {
            "embed": embed,
            "ephemeral": ephemeral,
        }
        if view is not None:
            kwargs["view"] = view
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
            return
        await interaction.response.send_message(**kwargs)

    def _generate_verification_code(self, length: int = 4) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _highrise_client(self) -> HighriseApiClient:
        return HighriseApiClient(
            base_url=self.cfg.highrise_api_base_url,
            api_key=self.cfg.highrise_api_key,
        )

    def _find_role(self, guild: discord.Guild, role_name: str) -> Optional[discord.Role]:
        target = normalize_role_name(role_name)
        for role in guild.roles:
            if normalize_role_name(role.name) == target:
                return role
        return None

    async def _apply_verified_access(self, member: discord.Member, highrise_username: str) -> tuple[bool, List[str]]:
        nickname_changed = False
        unlocked_roles: List[str] = []

        role_names = self.cfg.roles.get("verified_unlock", [])
        roles_to_add = []
        for role_name in role_names:
            role = self._find_role(member.guild, role_name)
            if role and role not in member.roles:
                roles_to_add.append(role)
                unlocked_roles.append(role.name)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Victor verification complete")
            except discord.Forbidden:
                self.logger.warning("Could not add verified unlock roles to %s", member.id)

        if member.nick != highrise_username:
            try:
                await member.edit(nick=highrise_username, reason="Victor verification complete")
                nickname_changed = True
            except discord.Forbidden:
                self.logger.warning("Could not update nickname for %s", member.id)

        return nickname_changed, unlocked_roles

    def _issue_verification_code(
        self,
        actor_id: str,
        member: discord.Member,
        profile: HighriseProfile,
    ) -> str:
        code = self._generate_verification_code()
        conn = db.get_connection(self.cfg.db_path)
        try:
            existing_user = db.fetch_user_by_discord_id(conn, str(member.id))
            linked = int(existing_user["linked"]) if existing_user else 0
            user_id = db.upsert_user(
                conn,
                str(member.id),
                profile.username,
                linked,
                highrise_user_id=profile.user_id,
            )
            db.upsert_verification_code(
                conn,
                user_id,
                profile.user_id,
                profile.username,
                code,
                "PENDING",
            )
            db.log_audit(
                conn,
                actor_id=actor_id,
                action="VERIFY_CODE_ISSUED",
                target_id=str(member.id),
                details=f"code={code}|username={profile.username}|highrise_user_id={profile.user_id}",
            )
            conn.commit()
        finally:
            conn.close()
        return code

    async def _complete_verification(
        self,
        actor_id: str,
        member: discord.Member,
        profile: HighriseProfile,
        *,
        bio_text: str,
        manual: bool = False,
    ) -> discord.Embed:
        conn = db.get_connection(self.cfg.db_path)
        try:
            user_id = db.upsert_user(
                conn,
                str(member.id),
                profile.username,
                1,
                highrise_user_id=profile.user_id,
            )
            db.mark_verification_success(conn, user_id)
            db.record_verification(
                conn,
                user_id,
                actor_id,
                bio_text,
                "PASS",
                [],
                [],
            )
            db.log_audit(
                conn,
                actor_id=actor_id,
                action="MANUAL_VERIFY" if manual else "VERIFY_PASS",
                target_id=str(member.id),
                details=f"username={profile.username}|highrise_user_id={profile.user_id}",
            )
            conn.commit()
        finally:
            conn.close()

        nickname_changed, unlocked_roles = await self._apply_verified_access(member, profile.username)
        return embeds.verify_success_embed(
            member.mention,
            profile.username,
            nickname_changed=nickname_changed,
            unlocked_roles=unlocked_roles,
            manual=manual,
        )

    def _status_payload(self, target: discord.Member) -> Optional[dict]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            user_row = db.fetch_user_by_discord_id(conn, str(target.id))
            if not user_row:
                return None
            code_row = db.fetch_verification_code(conn, int(user_row["id"]))
            last_ver = db.fetch_latest_verification(conn, int(user_row["id"]))
            return {
                "user_row": user_row,
                "code_row": code_row,
                "last_ver": last_ver,
            }
        finally:
            conn.close()

    def _build_status_embed(self, target: discord.Member, payload: dict) -> discord.Embed:
        user_row = payload["user_row"]
        code_row = payload["code_row"]
        last_ver = payload["last_ver"]

        if last_ver and last_ver.get("result") == "PASS":
            verified = "YES"
            state = "VERIFIED"
        elif code_row and code_row.get("status") == "MANUAL_REVIEW":
            verified = "REVIEW"
            state = "MANUAL REVIEW"
        elif code_row and code_row.get("status") == "PENDING":
            verified = "PENDING"
            state = "CODE ISSUED"
        else:
            verified = "NO"
            state = "UNVERIFIED"

        return embeds.status_embed(
            target.mention,
            user_row.get("highrise_username"),
            verified,
            state=state,
            code=code_row.get("code") if code_row and code_row.get("status") == "PENDING" else None,
            fail_count=code_row.get("fail_count") if code_row else None,
        )

    def _build_verify_view(self) -> VerifyConfirmView:
        return VerifyConfirmView(self)

    def _embed_field_value(self, embed: discord.Embed, field_name: str) -> Optional[str]:
        for field in embed.fields:
            if field.name == field_name:
                return field.value
        return None

    def _extract_target_member_id(self, embed: discord.Embed) -> Optional[int]:
        for field in embed.fields:
            if field.name == "[USER]":
                raw = (field.value or "").replace("<@", "").replace("!", "").replace(">", "").strip()
                if raw.isdigit():
                    return int(raw)
        return None

    async def _fetch_pending_profile(self, code_row: dict) -> HighriseProfile:
        client = self._highrise_client()
        highrise_user_id = str(code_row.get("highrise_user_id") or "").strip()
        highrise_username = str(code_row.get("highrise_username") or "").strip()
        if highrise_user_id:
            return await client.fetch_user_profile(highrise_user_id)
        return await client.fetch_profile_by_username(highrise_username)

    async def _issue_verify_flow(
        self,
        actor_id: str,
        member: discord.Member,
        highrise_username: str,
    ) -> discord.Embed:
        try:
            profile = await self._highrise_client().fetch_profile_by_username(highrise_username)
        except HighriseUserNotFound:
            return embeds.highrise_user_not_found_embed(highrise_username)
        except HighriseApiError as exc:
            self.logger.warning("Highrise API verify lookup failed for %s: %s", highrise_username, exc)
            return embeds.highrise_api_error_embed(str(exc))

        conn = db.get_connection(self.cfg.db_path)
        try:
            existing_user = db.fetch_user_by_discord_id(conn, str(member.id))
            user_id = db.upsert_user(
                conn,
                str(member.id),
                profile.username,
                int(existing_user["linked"]) if existing_user else 0,
                highrise_user_id=profile.user_id,
            )
            code_row = db.fetch_verification_code(conn, user_id)
            if code_row and str(code_row.get("highrise_username", "")).casefold() == profile.username.casefold():
                if str(code_row.get("status") or "").upper() == "MANUAL_REVIEW":
                    return embeds.verify_manual_review_embed(
                        member.mention,
                        profile.username,
                        int(code_row.get("fail_count") or 0),
                    )
                if str(code_row.get("status") or "").upper() == "VERIFIED":
                    return embeds.verify_success_embed(member.mention, profile.username)
                code = str(code_row.get("code") or "")
                if code:
                    return embeds.verify_code_embed(member.mention, profile.username, code)
            code = self._issue_verification_code(actor_id, member, profile)
            return embeds.verify_code_embed(member.mention, profile.username, code)
        finally:
            conn.close()

    async def _run_verify_check_flow(
        self,
        actor_id: str,
        member: discord.Member,
    ) -> tuple[discord.Embed, bool]:
        payload = self._status_payload(member)
        if not payload or not payload.get("code_row"):
            return embeds.not_found_embed(member.mention), True

        code_row = payload["code_row"]
        if str(code_row.get("status")) == "VERIFIED":
            return (
                embeds.verify_success_embed(
                    member.mention,
                    str(code_row.get("highrise_username") or "UNKNOWN"),
                ),
                True,
            )

        try:
            profile = await self._fetch_pending_profile(code_row)
        except HighriseApiError as exc:
            self.logger.warning("Highrise API confirm lookup failed for %s: %s", member.id, exc)
            return embeds.highrise_api_error_embed(str(exc)), False

        code = str(code_row.get("code") or "")
        if code and code.casefold() in (profile.bio or "").casefold():
            return (
                await self._complete_verification(
                    actor_id,
                    member,
                    profile,
                    bio_text=profile.bio or "",
                ),
                True,
            )

        conn = db.get_connection(self.cfg.db_path)
        try:
            user_row = db.fetch_user_by_discord_id(conn, str(member.id))
            if not user_row:
                return embeds.not_found_embed(member.mention), True
            user_id = int(user_row["id"])
            next_status = (
                "MANUAL_REVIEW"
                if int(code_row.get("fail_count") or 0) + 1 >= self.cfg.verification_max_failures
                else "PENDING"
            )
            fail_count = db.increment_verification_fail(
                conn,
                user_id,
                next_status,
                "Verification code missing from Highrise bio.",
            )
            db.record_verification(
                conn,
                user_id,
                actor_id,
                profile.bio or "",
                "FAIL",
                ["VERIFY_CODE_MISSING"],
                [],
            )
            db.log_audit(
                conn,
                actor_id=actor_id,
                action="VERIFY_FAIL",
                target_id=str(member.id),
                details=f"fail_count={fail_count}|username={profile.username}",
            )
            conn.commit()
        finally:
            conn.close()

        if fail_count >= self.cfg.verification_max_failures:
            await send_verify_review_post(
                self.bot,
                self.cfg,
                member=member,
                highrise_username=profile.username,
                fail_count=fail_count,
                code=code,
                last_error="Verification code missing from Highrise bio.",
                max_failures=self.cfg.verification_max_failures,
                bio_preview=(profile.bio or "")[:220] if profile.bio else "EMPTY BIO",
            )
            return embeds.verify_manual_review_embed(member.mention, profile.username, fail_count), True
        return (
            embeds.verify_retry_embed(
                member.mention,
                profile.username,
                code,
                fail_count,
                self.cfg.verification_max_failures,
            ),
            False,
        )

    async def handle_verify_confirm_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.message or not interaction.message.embeds:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        await interaction.response.defer()

        embed = interaction.message.embeds[0]
        member_id = self._extract_target_member_id(embed)
        if not member_id:
            await interaction.edit_original_response(embed=embeds.system_error_embed(), view=None)
            return

        target = interaction.guild.get_member(member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                await interaction.edit_original_response(embed=embeds.not_found_embed(str(member_id)), view=None)
                return

        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await interaction.edit_original_response(embed=embeds.permission_denied_embed("Verifier"), view=None)
            return

        allowed = actor.id == target.id or self._can_verify(actor)
        if not allowed:
            await interaction.edit_original_response(
                embed=embeds.permission_denied_embed("Verifier or target member"),
                view=None,
            )
            return

        result_embed, close_view = await self._run_verify_check_flow(str(actor.id), target)
        await interaction.edit_original_response(
            embed=result_embed,
            view=None if close_view else self._build_verify_view(),
        )

    async def handle_console_manual_verify_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.message or not interaction.message.embeds:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        actor = interaction.user
        if not isinstance(actor, discord.Member) or not self._can_verify(actor):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        embed = interaction.message.embeds[0]
        member_id = self._extract_target_member_id(embed)
        if not member_id:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        target = interaction.guild.get_member(member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(member_id)))
                return

        highrise_username = self._embed_field_value(embed, "[HIGHRISE]")
        profile = self._manual_profile_from_state(target, highrise_username)
        if not profile and highrise_username:
            profile = HighriseProfile(user_id="", username=highrise_username, bio="MANUAL_OVERRIDE")
        if not profile:
            await self._send_interaction_embed(
                interaction,
                embeds.urgent_embed(
                    "VERIFY REVIEW",
                    "Manual verification is only available after the member reaches manual review.",
                ),
            )
            return

        result = await self._complete_verification(
            str(actor.id),
            target,
            profile,
            bio_text="MANUAL_OVERRIDE",
            manual=True,
        )
        await self._send_interaction_embed(interaction, result)

    async def handle_console_status_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.message or not interaction.message.embeds:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        actor = interaction.user
        if not isinstance(actor, discord.Member) or not self._can_view_others(actor):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        member_id = self._extract_target_member_id(interaction.message.embeds[0])
        if not member_id:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        target = interaction.guild.get_member(member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(member_id)))
                return

        payload = self._status_payload(target)
        if not payload:
            await self._send_interaction_embed(interaction, embeds.not_found_embed(target.mention))
            return
        await self._send_interaction_embed(interaction, self._build_status_embed(target, payload))

    def _manual_profile_from_state(
        self,
        member: discord.Member,
        highrise_username: Optional[str],
    ) -> Optional[HighriseProfile]:
        payload = self._status_payload(member)
        user_row = payload["user_row"] if payload else None
        code_row = payload["code_row"] if payload else None
        if code_row and str(code_row.get("status")) not in {"MANUAL_REVIEW", "VERIFIED"} and not highrise_username:
            return None
        username = (highrise_username or (user_row or {}).get("highrise_username") or (code_row or {}).get("highrise_username"))
        if not username:
            return None
        return HighriseProfile(
            user_id=str((user_row or {}).get("highrise_user_id") or (code_row or {}).get("highrise_user_id") or ""),
            username=str(username),
            bio="MANUAL_OVERRIDE",
        )

    @commands.command(name="verify")
    async def verify(self, ctx: commands.Context, member: discord.Member, highrise_username: str) -> None:
        if not self._can_verify(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Verifier"))
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        target_blacklist = self._blacklist_record(str(member.id))
        if target_blacklist and not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.blacklisted_embed(target_blacklist.get("reason")))
            return

        await ctx.trigger_typing()
        embed = await self._issue_verify_flow(str(ctx.author.id), member, highrise_username)
        view = self._build_verify_view() if embed.title == embeds.TITLE_VERIFY and any(field.name == "[CODE]" for field in embed.fields) else None
        await ctx.send(embed=embed, view=view)

    @commands.command(name="manualverify")
    async def manual_verify(
        self,
        ctx: commands.Context,
        member: discord.Member,
        highrise_username: Optional[str] = None,
    ) -> None:
        if not self._can_verify(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Verifier"))
            return

        profile = self._manual_profile_from_state(member, highrise_username)
        if not profile:
            await ctx.send(
                embed=embeds.urgent_embed(
                    "VERIFY REVIEW",
                    "Manual verification is only available after the member reaches manual review, unless you provide a username override.",
                )
            )
            return

        embed = await self._complete_verification(
            str(ctx.author.id),
            member,
            profile,
            bio_text="MANUAL_OVERRIDE",
            manual=True,
        )
        await ctx.send(embed=embed)

    @commands.command(name="status")
    async def status(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        target = member or ctx.author
        if member and member != ctx.author and not self._can_view_others(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Verifier"))
            return

        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        payload = self._status_payload(target)
        if not payload:
            await ctx.send(embed=embeds.not_found_embed(target.mention))
            return
        await ctx.send(embed=self._build_status_embed(target, payload))

    @app_commands.command(name="verify", description="Issue or check a Highrise verification code for a member.")
    @app_commands.describe(member="Discord member to verify", highrise_username="Highrise username to verify")
    @app_commands.guild_only()
    async def verify_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        highrise_username: str,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return
        if not self._can_verify(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        target_blacklist = self._blacklist_record(str(member.id))
        if target_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(target_blacklist.get("reason")))
            return

        await interaction.response.defer(ephemeral=False, thinking=True)
        embed = await self._issue_verify_flow(str(author.id), member, highrise_username)
        view = self._build_verify_view() if embed.title == embeds.TITLE_VERIFY and any(field.name == "[CODE]" for field in embed.fields) else None
        await self._send_interaction_embed(interaction, embed, ephemeral=False, view=view)

    @app_commands.command(name="manualverify", description="Manually approve a member after failed Highrise checks.")
    @app_commands.describe(member="Discord member to approve", highrise_username="Optional Highrise username override")
    @app_commands.guild_only()
    async def manual_verify_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        highrise_username: Optional[str] = None,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return
        if not self._can_verify(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        profile = self._manual_profile_from_state(member, highrise_username)
        if not profile:
            await self._send_interaction_embed(
                interaction,
                embeds.urgent_embed(
                    "VERIFY REVIEW",
                    "Manual verification is only available after the member reaches manual review, unless you provide a username override.",
                ),
            )
            return

        embed = await self._complete_verification(
            str(author.id),
            member,
            profile,
            bio_text="MANUAL_OVERRIDE",
            manual=True,
        )
        await self._send_interaction_embed(interaction, embed)

    @app_commands.command(name="status", description="Check Victor verification status for yourself or another member.")
    @app_commands.describe(member="Optional member to look up")
    @app_commands.guild_only()
    async def status_slash(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        target = member or author
        if member and member != author and not self._can_view_others(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        author_blacklist = self._blacklist_record(str(author.id))
        if author_blacklist and not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        payload = self._status_payload(target)
        if not payload:
            await self._send_interaction_embed(interaction, embeds.not_found_embed(target.mention))
            return
        await self._send_interaction_embed(interaction, self._build_status_embed(target, payload))


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    cog = VerifyCog(bot, cfg)
    await bot.add_cog(cog)
    bot.add_view(VerifyConfirmView(cog))
