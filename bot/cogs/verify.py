import logging
from typing import List, Optional

import discord
from discord.ext import commands

from bot import db
from bot import embeds
from bot.cogs.staff_console import send_verify_intake_review_post
from bot.config import Config
from bot.utils.command_logging import log_command_event, log_system_event
from bot.utils.permissions import has_any_role, normalize_role_name

VERIFY_BEGIN_BUTTON_ID = "victor:verify_begin"
AUTO_VERIFY_FLAG = "autoverify"


class VerifyIntakeModal(discord.ui.Modal):
    def __init__(self, cog: "VerifyCog", target_member_id: int, existing_username: Optional[str] = None) -> None:
        super().__init__(title="victor.verify // intake")
        self.cog = cog
        self.target_member_id = target_member_id
        self.highrise_username = discord.ui.TextInput(
            label="Highrise username",
            placeholder="drop your HR username here",
            default=existing_username or "",
            min_length=2,
            max_length=32,
            required=True,
        )
        self.add_item(self.highrise_username)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_verify_modal_submit(
            interaction,
            self.target_member_id,
            str(self.highrise_username),
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await self.cog.handle_verify_component_error(
            interaction,
            error,
            stage="verify_modal",
        )


class VerifyBeginView(discord.ui.View):
    def __init__(self, cog: "VerifyCog") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Open Intake",
        style=discord.ButtonStyle.success,
        emoji="🕯️",
        custom_id=VERIFY_BEGIN_BUTTON_ID,
    )
    async def begin_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.handle_verify_begin_button(interaction)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        await self.cog.handle_verify_component_error(
            interaction,
            error,
            stage=f"verify_begin_button:{item.custom_id or 'unknown'}",
        )


class VerifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg
        self.logger = logging.getLogger("victor.verify")
        self._prompt_messages: dict[tuple[int, int], discord.Message] = {}

    def _has_any_role(self, member: discord.Member, role_names: List[str]) -> bool:
        return has_any_role(member.roles, role_names)

    def _is_owner(self, member: discord.Member) -> bool:
        return self._has_any_role(member, self.cfg.roles.get("owner", []))

    def _is_admin(self, member: discord.Member) -> bool:
        if self._is_owner(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("admin", []))

    def _can_manage_verification(self, member: discord.Member) -> bool:
        if self._is_admin(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("verifier", []))

    def _can_view_others(self, member: discord.Member) -> bool:
        return self._can_manage_verification(member)

    def _blacklist_record(self, discord_id: str) -> Optional[dict]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            return db.is_blacklisted(conn, discord_id)
        finally:
            conn.close()

    def _verify_channel_mention(self) -> Optional[str]:
        if not self.cfg.verify_channel_id:
            return None
        return f"<#{self.cfg.verify_channel_id}>"

    def _auto_verify_enabled(self) -> bool:
        conn = db.get_connection(self.cfg.db_path)
        try:
            return db.get_feature_flag(conn, AUTO_VERIFY_FLAG, "0") == "1"
        finally:
            conn.close()

    async def _send_verify_lane_notice(
        self,
        guild: discord.Guild,
        member: discord.Member,
        embed: discord.Embed,
    ) -> None:
        channel_id = self.cfg.verify_channel_id
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                return

        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(content=member.mention, embed=embed)
            except (discord.HTTPException, discord.Forbidden):
                return

    def _is_verify_channel(self, channel_id: Optional[int]) -> bool:
        if not self.cfg.verify_channel_id:
            return True
        return channel_id == self.cfg.verify_channel_id

    async def _redirect_to_verify_channel_for_context(self, ctx: commands.Context) -> bool:
        if not ctx.guild or self._is_verify_channel(getattr(ctx.channel, "id", None)):
            return False
        mention = self._verify_channel_mention()
        if mention:
            await ctx.send(embed=embeds.verify_channel_redirect_embed(mention))
            return True
        return False

    async def _redirect_to_verify_channel_for_interaction(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or self._is_verify_channel(interaction.channel_id):
            return False
        mention = self._verify_channel_mention()
        if mention:
            await self._send_interaction_embed(interaction, embeds.verify_channel_redirect_embed(mention), ephemeral=True)
            return True
        return False

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

    async def _defer_interaction(self, interaction: discord.Interaction, *, ephemeral: bool = True) -> None:
        if interaction.response.is_done():
            return
        await interaction.response.defer(ephemeral=ephemeral)

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
                await member.add_roles(*roles_to_add, reason="Victor verify intake complete")
            except discord.Forbidden:
                self.logger.warning("Could not add verified unlock roles to %s", member.id)

        return nickname_changed, unlocked_roles

    def _special_role_note(self, member: discord.Member) -> Optional[str]:
        for key, label in (("founder", "Founder"), ("owner", "Owner"), ("admin", "Admin")):
            roles = self.cfg.roles.get(key, [])
            if roles and self._has_any_role(member, roles):
                return f"Quick install recognition: {label} status noted on this intake."
        return None

    def _status_guidance(self, verification_status: str, code_row: Optional[dict]) -> str:
        lane = self._verify_channel_mention() or "the hr-id lane"
        status = (verification_status or "").upper()
        if status in {"USERNAME LOGGED", "VERIFIED"}:
            return "You're verified. Keep the bio intact and let staff know if you need changes."
        if status == "PENDING":
            return "Staff is reviewing the intake. Stand by for the console to post the result."
        if status == "RETRY REQUESTED":
            return f"Staff requested a cleaner username. Update the entry and run `!verify` in {lane} again."
        if status == "REJECTED":
            return f"Staff rejected the intake. Fix the username and resubmit with `!verify` inside {lane}."
        return f"No intake logged. Run `!verify` inside {lane} or use the Verify button from `!menu`."

    def _trusted_roles(self, member: discord.Member) -> List[str]:
        trusted: List[str] = []
        if not member.guild:
            return trusted
        for key in ("seller", "buyer"):
            for role_name in self.cfg.roles.get(key, []):
                role = self._find_role(member.guild, role_name)
                if role and role in member.roles and role.name not in trusted:
                    trusted.append(role.name)
        return trusted

    def _prompt_key(self, member: discord.Member) -> Optional[tuple[int, int]]:
        if not member.guild:
            return None
        return (member.guild.id, member.id)

    async def _cleanup_previous_prompt(self, member: discord.Member) -> None:
        key = self._prompt_key(member)
        if not key:
            return
        previous = self._prompt_messages.pop(key, None)
        if previous:
            await self._delete_message_safely(previous)

    def _track_prompt_message(self, member: discord.Member, message: discord.Message) -> None:
        key = self._prompt_key(member)
        if not key:
            return
        self._prompt_messages[key] = message

    def _forget_prompt_message(self, member: discord.Member) -> None:
        key = self._prompt_key(member)
        if not key:
            return
        self._prompt_messages.pop(key, None)

    async def _delete_message_safely(self, message: Optional[discord.Message]) -> None:
        if message is None:
            return
        try:
            await message.delete()
        except discord.HTTPException:
            self.logger.debug("Could not delete intake message %s", getattr(message, "id", "unknown"))

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
        verification_status = str((code_row or {}).get("status") or "").upper()

        if verification_status == "PENDING":
            verified = "PENDING"
            state = "STAFF REVIEW"
        elif verification_status == "REJECTED":
            verified = "NO"
            state = "RETRY REQUESTED"
        elif last_ver and last_ver.get("result") == "PASS":
            verified = "YES"
            state = "USERNAME LOGGED"
        elif verification_status == "VERIFIED":
            verified = "YES"
            state = "USERNAME LOGGED"
        else:
            verified = "NO"
            state = "NO DATA"

        highrise_username = (
            (code_row or {}).get("highrise_username")
            or user_row.get("highrise_username")
        )
        trusted_roles = self._trusted_roles(target)
        db_code = (code_row or {}).get("code")
        db_status = (code_row or {}).get("status")
        guidance = self._status_guidance(verification_status, code_row)
        return embeds.status_embed(
            target.mention,
            highrise_username,
            verified,
            state=state,
            code=db_code,
            fail_count=code_row.get("fail_count") if code_row else None,
            trusted_roles=trusted_roles,
            db_status=db_status,
            guidance=guidance,
        )

    def _build_verify_view(self) -> VerifyBeginView:
        return VerifyBeginView(self)

    async def _log_verify_runtime_error(
        self,
        interaction: discord.Interaction,
        *,
        stage: str,
        error: Exception,
    ) -> None:
        user_id = getattr(interaction.user, "id", 0)
        location = str(interaction.guild.id) if interaction.guild else "dm"
        await log_command_event(
            self.bot,
            self.cfg,
            "fail",
            "prefix",
            user_id,
            "verify",
            location,
            details=f"{stage}: {type(error).__name__}: {error}",
            level=logging.ERROR,
            publish_to_channel=False,
        )

    async def handle_verify_component_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        *,
        stage: str,
    ) -> None:
        self.logger.exception("Verify intake interaction failed during %s", stage, exc_info=error)
        await self._log_verify_runtime_error(interaction, stage=stage, error=error)
        try:
            await self._send_interaction_embed(interaction, embeds.system_error_embed(), ephemeral=True)
        except discord.HTTPException:
            return

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

    def _normalize_highrise_username(self, raw_value: str) -> Optional[str]:
        value = (raw_value or "").strip()
        if value.startswith("@"):
            value = value[1:].strip()
        if not value or any(char.isspace() for char in value):
            return None
        return value

    async def _resolve_target_member(
        self,
        interaction: discord.Interaction,
        actor: discord.Member,
        *,
        allow_actor_fallback: bool = False,
    ) -> Optional[discord.Member]:
        target_member_id: Optional[int] = None
        if interaction.message and interaction.message.embeds:
            target_member_id = self._extract_target_member_id(interaction.message.embeds[0])

        if not target_member_id:
            if allow_actor_fallback and not self._can_manage_verification(actor):
                return actor
            return None

        target = interaction.guild.get_member(target_member_id) if interaction.guild else None
        if target is None and interaction.guild is not None:
            try:
                target = await interaction.guild.fetch_member(target_member_id)
            except discord.HTTPException:
                return None
        return target

    def _existing_username(self, member: discord.Member) -> Optional[str]:
        payload = self._status_payload(member)
        if not payload:
            return None
        return (
            str((payload.get("code_row") or {}).get("highrise_username") or "").strip()
            or str(payload["user_row"].get("highrise_username") or "").strip()
            or None
        )

    def _build_verify_prompt_embed(self, member: discord.Member) -> discord.Embed:
        return embeds.verify_prompt_embed(member.mention, existing_username=self._existing_username(member))

    async def _queue_highrise_username_submission(
        self,
        actor_id: str,
        member: discord.Member,
        highrise_username: str,
        *,
        source: str,
    ) -> discord.Embed:
        conn = db.get_connection(self.cfg.db_path)
        previous_username: Optional[str] = None
        try:
            previous = db.fetch_user_by_discord_id(conn, str(member.id))
            previous_username = str((previous or {}).get("highrise_username") or "").strip() or None
            user_id = db.upsert_user(
                conn,
                str(member.id),
                previous_username or highrise_username,
                int((previous or {}).get("linked") or 0),
                highrise_user_id=(previous or {}).get("highrise_user_id"),
            )
            db.queue_verification_review(conn, user_id, highrise_username)
            db.log_audit(
                conn,
                actor_id=actor_id,
                action="VERIFY_USERNAME_SUBMITTED",
                target_id=str(member.id),
                details=(
                    f"username={highrise_username}|source={source}|"
                    f"previous_username={previous_username or 'NONE'}"
                ),
            )
            conn.commit()
        finally:
            conn.close()

        if self._auto_verify_enabled():
            embed = await self._approve_highrise_username(
                actor_id,
                member,
                highrise_username,
                source="auto_verify",
            )
            await log_system_event(
                self.bot,
                self.cfg,
                "Auto Verify",
                details=f"member={member.id} highrise={highrise_username}",
            )
            return embed

        await send_verify_intake_review_post(
            self.bot,
            self.cfg,
            member=member,
            highrise_username=highrise_username,
            submitted_by_id=int(actor_id),
            previous_username=previous_username,
        )
        return embeds.verify_submission_received_embed(member.mention, highrise_username)

    async def _approve_highrise_username(
        self,
        actor_id: str,
        member: discord.Member,
        highrise_username: str,
        *,
        source: str,
        manual: bool = False,
        staff_view: bool = False,
    ) -> discord.Embed:
        conn = db.get_connection(self.cfg.db_path)
        try:
            previous = db.fetch_user_by_discord_id(conn, str(member.id))
            user_id = db.upsert_user(
                conn,
                str(member.id),
                highrise_username,
                1,
                highrise_user_id=None,
            )
            db.upsert_verification_code(
                conn,
                user_id,
                None,
                highrise_username,
                "SELF-REPORTED",
                "VERIFIED",
            )
            db.mark_verification_success(conn, user_id)
            db.record_verification(
                conn,
                user_id,
                actor_id,
                f"SELF_REPORTED_USERNAME:{highrise_username}",
                "PASS",
                [],
                [],
            )
            db.log_audit(
                conn,
                actor_id=actor_id,
                action="MANUAL_VERIFY" if manual else "VERIFY_USERNAME_CAPTURED",
                target_id=str(member.id),
                details=(
                    f"username={highrise_username}|source={source}|"
                    f"previous_username={(previous or {}).get('highrise_username') or 'NONE'}"
                ),
            )
            conn.commit()
        finally:
            conn.close()

        nickname_changed, unlocked_roles = await self._apply_verified_access(member, highrise_username)
        recognition_note = self._special_role_note(member)
        trusted_roles = self._trusted_roles(member)

        approval_notice = embeds.approval_dm_embed(highrise_username)
        try:
            await member.send(embed=approval_notice)
        except discord.HTTPException:
            self.logger.info("Could not DM approval notice to %s", member.id)

        public_notice = embeds.verify_staff_approved_embed(member.mention, highrise_username)
        await self._send_verify_lane_notice(member.guild, member, public_notice)

        if trusted_roles:
            await log_system_event(
                self.bot,
                self.cfg,
                "Trusted Member Verified",
                details=(
                    f"user={member.id} | roles={','.join(trusted_roles)} | "
                    f"highrise={highrise_username}"
                ),
                level=logging.INFO,
                publish_to_channel=True,
            )

        if manual:
            return embeds.manual_verify_ready_embed(member.mention, highrise_username)
        if staff_view:
            return embeds.verify_staff_action_result_embed(
                "approved",
                member.mention,
                channel_mention=self._verify_channel_mention(),
            )
        return embeds.verify_success_embed(
            member.mention,
            highrise_username,
            nickname_changed=nickname_changed,
            unlocked_roles=unlocked_roles,
            manual=manual,
            captured=not manual,
            recognition_note=recognition_note,
            trusted_roles=trusted_roles,
        )

    async def _reject_highrise_username(
        self,
        actor_id: str,
        member: discord.Member,
        highrise_username: str,
        *,
        source: str,
    ) -> discord.Embed:
        conn = db.get_connection(self.cfg.db_path)
        try:
            user_row = db.fetch_user_by_discord_id(conn, str(member.id))
            if not user_row:
                return embeds.verify_missing_record_embed(member.mention)
            db.increment_verification_fail(conn, int(user_row["id"]), "REJECTED", "Rejected by staff review.")
            db.log_audit(
                conn,
                actor_id=actor_id,
                action="VERIFY_USERNAME_REJECTED",
                target_id=str(member.id),
                details=f"username={highrise_username}|source={source}",
            )
            conn.commit()
        finally:
            conn.close()

        rejection_embed = embeds.rejection_dm_embed(highrise_username)
        try:
            await member.send(embed=rejection_embed)
        except discord.HTTPException:
            self.logger.info("Could not DM rejection notice to %s", member.id)
        await self._send_verify_lane_notice(
            member.guild,
            member,
            embeds.verify_rejected_embed(member.mention, highrise_username),
        )
        return embeds.verify_staff_action_result_embed(
            "rejected",
            member.mention,
            channel_mention=self._verify_channel_mention(),
        )

    async def _send_verify_prompt_to_context(self, ctx: commands.Context, member: discord.Member) -> None:
        await self._cleanup_previous_prompt(member)
        embed = self._build_verify_prompt_embed(member)
        message = await ctx.send(embed=embed, view=self._build_verify_view())
        self._track_prompt_message(member, message)

    async def handle_plain_text_verify_trigger(self, message: discord.Message) -> bool:
        if not message.guild or not isinstance(message.author, discord.Member):
            return False

        if not self._is_verify_channel(getattr(message.channel, "id", None)):
            mention = self._verify_channel_mention()
            if mention:
                await message.reply(
                    embed=embeds.verify_channel_redirect_embed(mention),
                    mention_author=False,
                    delete_after=20,
                )
                return True
            return False

        author_blacklist = self._blacklist_record(str(message.author.id))
        if author_blacklist and not self._is_admin(message.author):
            await message.reply(
                embed=embeds.blacklisted_embed(author_blacklist.get("reason")),
                mention_author=False,
                delete_after=20,
            )
            return True

        await self._cleanup_previous_prompt(message.author)
        reply = await message.reply(
            embed=self._build_verify_prompt_embed(message.author),
            view=self._build_verify_view(),
            mention_author=False,
            delete_after=60,
        )
        self._track_prompt_message(message.author, reply)
        return True

    async def _send_verify_prompt_to_interaction(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        *,
        ephemeral: bool = True,
    ) -> None:
        embed = self._build_verify_prompt_embed(member)
        await self._send_interaction_embed(interaction, embed, ephemeral=ephemeral, view=self._build_verify_view())

    async def handle_verify_begin_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Server member"))
            return

        target = await self._resolve_target_member(interaction, actor, allow_actor_fallback=True)
        if target is None:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("Run `!verify` again to open a fresh intake prompt, then press `Open Intake` there."),
            )
            return

        if actor.id != target.id and not self._can_manage_verification(actor):
            await self._send_interaction_embed(
                interaction,
                embeds.permission_denied_embed("Target member or verifier"),
            )
            return

        author_blacklist = self._blacklist_record(str(actor.id))
        if author_blacklist and not self._is_admin(actor):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        try:
            await interaction.response.send_modal(
                VerifyIntakeModal(
                    self,
                    target.id,
                    existing_username=self._existing_username(target),
                )
            )
        except Exception as exc:
            await self.handle_verify_component_error(interaction, exc, stage="verify_begin_button:send_modal")

    async def handle_verify_modal_submit(
        self,
        interaction: discord.Interaction,
        target_member_id: int,
        raw_username: str,
    ) -> None:
        if not interaction.guild:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Server member"))
            return

        await self._defer_interaction(interaction, ephemeral=True)

        target = interaction.guild.get_member(target_member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(target_member_id)
            except discord.HTTPException:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(target_member_id)))
                return

        if actor.id != target.id and not self._can_manage_verification(actor):
            await self._send_interaction_embed(
                interaction,
                embeds.permission_denied_embed("Target member or verifier"),
            )
            return

        author_blacklist = self._blacklist_record(str(actor.id))
        if author_blacklist and not self._is_admin(actor):
            await self._send_interaction_embed(interaction, embeds.blacklisted_embed(author_blacklist.get("reason")))
            return

        username = self._normalize_highrise_username(raw_username)
        if not username:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("Use a clean Highrise username with no spaces, like `ExampleUser`."),
            )
            return

        try:
            embed = await self._queue_highrise_username_submission(
                str(actor.id),
                target,
                username,
                source="intake_modal",
            )
        except Exception as exc:
            await self.handle_verify_component_error(interaction, exc, stage="verify_modal:queue_submission")
            return

        await self._send_interaction_embed(interaction, embed, ephemeral=True)
        await self._delete_message_safely(interaction.message)
        self._forget_prompt_message(target)

    async def handle_menu_verify_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return
        if await self._redirect_to_verify_channel_for_interaction(interaction):
            return
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Server member"))
            return
        await self._send_verify_prompt_to_interaction(interaction, actor, ephemeral=True)

    async def handle_menu_status_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return
        if await self._redirect_to_verify_channel_for_interaction(interaction):
            return
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Server member"))
            return
        payload = self._status_payload(actor)
        if not payload:
            await self._send_interaction_embed(interaction, embeds.verify_missing_record_embed(actor.mention), ephemeral=True)
            return
        await self._send_interaction_embed(interaction, self._build_status_embed(actor, payload), ephemeral=True)

    async def handle_console_manual_verify_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.message or not interaction.message.embeds:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        actor = interaction.user
        if not isinstance(actor, discord.Member) or not self._can_manage_verification(actor):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        embed = interaction.message.embeds[0]
        member_id = self._extract_target_member_id(embed)
        if not member_id:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        await self._defer_interaction(interaction, ephemeral=True)

        target = interaction.guild.get_member(member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(member_id)))
                return

        highrise_username = self._embed_field_value(embed, "[HIGHRISE]") or self._existing_username(target)
        username = self._normalize_highrise_username(highrise_username or "")
        if not username:
            await self._send_interaction_embed(
                interaction,
                embeds.invalid_usage_embed("Staff needs a Highrise username on file before manual verify can stamp this through."),
            )
            return

        result = await self._approve_highrise_username(
            str(actor.id),
            target,
            username,
            source="staff_console",
            manual=True,
        )
        await self._send_interaction_embed(interaction, result)

    async def handle_console_accept_username_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.message or not interaction.message.embeds:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        actor = interaction.user
        if not isinstance(actor, discord.Member) or not self._can_manage_verification(actor):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        embed = interaction.message.embeds[0]
        member_id = self._extract_target_member_id(embed)
        username = self._normalize_highrise_username(self._embed_field_value(embed, "[HIGHRISE]") or "")
        if not member_id or not username:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        await self._defer_interaction(interaction, ephemeral=True)

        target = interaction.guild.get_member(member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(member_id)))
                return

        result = await self._approve_highrise_username(
            str(actor.id),
            target,
            username,
            source="staff_console_accept",
            manual=False,
            staff_view=True,
        )
        await self._send_interaction_embed(interaction, result)
        await self._delete_message_safely(interaction.message)

    async def handle_console_reject_username_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.message or not interaction.message.embeds:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        actor = interaction.user
        if not isinstance(actor, discord.Member) or not self._can_manage_verification(actor):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Verifier"))
            return

        embed = interaction.message.embeds[0]
        member_id = self._extract_target_member_id(embed)
        username = self._normalize_highrise_username(self._embed_field_value(embed, "[HIGHRISE]") or "")
        if not member_id or not username:
            await self._send_interaction_embed(interaction, embeds.system_error_embed())
            return

        await self._defer_interaction(interaction, ephemeral=True)

        target = interaction.guild.get_member(member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(member_id)))
                return

        result = await self._reject_highrise_username(
            str(actor.id),
            target,
            username,
            source="staff_console_reject",
        )
        await self._send_interaction_embed(interaction, result)
        await self._delete_message_safely(interaction.message)

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

        await self._defer_interaction(interaction, ephemeral=True)

        target = interaction.guild.get_member(member_id)
        if target is None:
            try:
                target = await interaction.guild.fetch_member(member_id)
            except discord.HTTPException:
                await self._send_interaction_embed(interaction, embeds.not_found_embed(str(member_id)))
                return

        payload = self._status_payload(target)
        if not payload:
            await self._send_interaction_embed(interaction, embeds.verify_missing_record_embed(target.mention))
            return
        await self._send_interaction_embed(interaction, self._build_status_embed(target, payload))

    @commands.command(name="autoverify")
    async def auto_verify(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        highrise_username: Optional[str] = None,
    ) -> None:
        if not self._can_manage_verification(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Verifier"))
            return

        username_text = self._normalize_highrise_username(highrise_username or self._existing_username(member) or "")
        if not username_text:
            await ctx.send(
                embed=embeds.invalid_usage_embed("!autoverify @user username"),
            )
            return

        embed = await self._approve_highrise_username(
            str(ctx.author.id),
            member,
            username_text,
            source="autoverify_command",
            manual=True,
        )
        await ctx.send(embed=embed)

    @commands.command(name="verify")
    async def verify(self, ctx: commands.Context) -> None:
        if await self._redirect_to_verify_channel_for_context(ctx):
            return
        author_blacklist = self._blacklist_record(str(ctx.author.id))
        if author_blacklist and not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.blacklisted_embed(author_blacklist.get("reason")))
            return
        await self._send_verify_prompt_to_context(ctx, ctx.author)

    @commands.command(name="manualverify")
    async def manual_verify(
        self,
        ctx: commands.Context,
        member: discord.Member,
        highrise_username: Optional[str] = None,
    ) -> None:
        if await self._redirect_to_verify_channel_for_context(ctx):
            return
        if not self._can_manage_verification(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Verifier"))
            return

        username = self._normalize_highrise_username(highrise_username or self._existing_username(member) or "")
        if not username:
            await ctx.send(
                embed=embeds.invalid_usage_embed("!manualverify @user username"),
            )
            return

        embed = await self._approve_highrise_username(
            str(ctx.author.id),
            member,
            username,
            source="manual_command",
            manual=True,
        )
        await ctx.send(embed=embed)

    @commands.command(name="status")
    async def status(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        if await self._redirect_to_verify_channel_for_context(ctx):
            return
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
            await ctx.send(embed=embeds.verify_missing_record_embed(target.mention))
            return
        await ctx.send(embed=self._build_status_embed(target, payload))

async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    cog = VerifyCog(bot, cfg)
    await bot.add_cog(cog)
    bot.add_view(VerifyBeginView(cog))
