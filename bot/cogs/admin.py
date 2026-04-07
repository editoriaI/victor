from typing import Callable, Optional

AUTO_SYNC_FLAG = "autosync"
AUTO_VERIFY_FLAG = "autoverify"

import discord
from discord import app_commands
from discord.ext import commands

from bot import db, embeds
from bot.config import Config
from bot.utils.permissions import has_any_role


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg
# helper methods after?

    def _has_any_role(self, member: discord.Member, role_names: list) -> bool:
        return has_any_role(member.roles, role_names)

    def _is_owner(self, member: discord.Member) -> bool:
        return self._has_any_role(member, self.cfg.roles.get("owner", []))

    def _is_admin(self, member: discord.Member) -> bool:
        if self._is_owner(member):
            return True
        return self._has_any_role(member, self.cfg.roles.get("admin", []))

    def _get_flag(self, flag: str) -> bool:
        conn = db.get_connection(self.cfg.db_path)
        try:
            return db.get_feature_flag(conn, flag) == "1"
        finally:
            conn.close()

    def _set_flag(self, flag: str, enable: bool) -> None:
        conn = db.get_connection(self.cfg.db_path)
        try:
            db.set_feature_flag(conn, flag, "1" if enable else "0")
            conn.commit()
        finally:
            conn.close()

    def _is_auto_sync_enabled(self) -> bool:
        return self._get_flag(AUTO_SYNC_FLAG)

    def _set_auto_sync(self, enable: bool) -> None:
        self._set_flag(AUTO_SYNC_FLAG, enable)

    def _is_auto_verify_enabled(self) -> bool:
        return self._get_flag(AUTO_VERIFY_FLAG)

    def _set_auto_verify(self, enable: bool) -> None:
        self._set_flag(AUTO_VERIFY_FLAG, enable)

    async def _send_interaction_embed(
        self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = True
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    async def _defer_interaction(self, interaction: discord.Interaction, *, ephemeral: bool = True) -> None:
        if interaction.response.is_done():
            return
        await interaction.response.defer(ephemeral=ephemeral)

    async def _run_sync_action(self) -> discord.Embed:
        synced = await self.bot.tree.sync()
        return embeds.sync_success_embed(len(synced))

    def _autosync_state_embed(self, enable: bool) -> discord.Embed:
        state_text = "ENABLED" if enable else "DISABLED"
        embed = embeds.make_embed(
            embeds.TITLE_ADMIN,
            f"[ AUTO SYNC {state_text} ]\n\nVictor will now {'run' if enable else 'skip'} an automatic sync on startup.",
            embeds.COLOR_OK if enable else embeds.COLOR_WARN,
        )
        embed.add_field(name="[STATE]", value=state_text, inline=True)
        return embed

    def _autoverify_state_embed(self, enable: bool) -> discord.Embed:
        state_text = "ENABLED" if enable else "DISABLED"
        embed = embeds.make_embed(
            embeds.TITLE_ADMIN,
            f"[ AUTO VERIFY {state_text} ]\n\nVictor will now {'auto-approve' if enable else 'require'} intake submissions.",
            embeds.COLOR_OK if enable else embeds.COLOR_WARN,
        )
        embed.add_field(name="[STATE]", value=state_text, inline=True)
        return embed

    async def _purge_victor_messages(
        self,
        channel: discord.abc.Messageable,
        *,
        lookback: int,
        include_message_ids: Optional[set[int]] = None,
    ) -> int:
        include_ids = include_message_ids or set()
        bot_user = self.bot.user
        if bot_user is None:
            return 0

        deleted = 0
        async for message in channel.history(limit=lookback):
            if message.author.id != bot_user.id and message.id not in include_ids:
                continue
            try:
                await message.delete()
            except discord.HTTPException:
                continue
            deleted += 1
        return deleted

    def _purge_complete_embed(self, deleted_count: int, lookback: int) -> discord.Embed:
        embed = embeds.make_embed(
            embeds.TITLE_ADMIN,
            (
                "[ PURGE COMPLETE ]\n\n"
                f"Victor cleared {deleted_count} post{'s' if deleted_count != 1 else ''} from the last {lookback} message"
                f"{'s' if lookback != 1 else ''} in this channel."
            ),
            embeds.COLOR_OK,
        )
        embed.add_field(name="[DELETED]", value=str(deleted_count), inline=True)
        embed.add_field(name="[LOOKBACK]", value=str(lookback), inline=True)
        return embed

    async def _flag_action_embed(
        self,
        interaction: discord.Interaction,
        *,
        title: str,
        description: str,
        enabled: bool,
        handler: Callable[[bool], None],
    ) -> None:
        handler(enabled)
        state_text = "ENABLED" if enabled else "DISABLED"
        embed = embeds.make_embed(
            embeds.TITLE_ADMIN,
            description,
            embeds.COLOR_OK if enabled else embeds.COLOR_WARN,
        )
        embed.add_field(name="[STATE]", value=state_text, inline=True)
        await self._send_interaction_embed(interaction, embed)

    async def handle_auto_sync_toggle(self, interaction: discord.Interaction, enable: bool) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return
        self._set_auto_sync(enable)
        await self._send_interaction_embed(interaction, self._autosync_state_embed(enable), ephemeral=True)

    async def handle_auto_verify_toggle(self, interaction: discord.Interaction, enable: bool) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return
        self._set_auto_verify(enable)
        await self._send_interaction_embed(interaction, self._autoverify_state_embed(enable), ephemeral=True)

    async def handle_apply_fix_action(self, interaction: discord.Interaction, action: str) -> bool:
        actor = interaction.user
        if not isinstance(actor, discord.Member) or not self._is_admin(actor):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return True

        normalized = (action or "").strip().casefold()
        if normalized == "sync":
            await self.handle_console_sync_button(interaction)
            return True
        if normalized in {"autoverify", "auto verify"}:
            await self._flag_action_embed(
                interaction,
                title="AUTO VERIFY",
                description="Victor will now auto-approve usernames that pass the intake checks.",
                enabled=True,
                handler=lambda value: self._set_auto_verify(value),
            )
            return True
        if normalized in {"autosync", "auto sync"}:
            await self._flag_action_embed(
                interaction,
                title="AUTO SYNC",
                description="Victor will sync slash commands automatically on startup.",
                enabled=True,
                handler=lambda value: self._set_auto_sync(value),
            )
            return True
        return False

    async def handle_console_sync_button(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return
        await self._defer_interaction(interaction, ephemeral=True)
        embed = await self._run_sync_action()
        await self._send_interaction_embed(interaction, embed)

    @commands.command(name="purge")
    async def purge_messages(self, ctx: commands.Context, lookback: Optional[int] = 100) -> None:
        if not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Victor Admin"))
            return

        if not ctx.guild or not isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
            await ctx.send(embed=embeds.invalid_usage_embed("!purge [lookback]"))
            return

        lookback = int(lookback or 100)
        if lookback < 1 or lookback > 500:
            await ctx.send(embed=embeds.invalid_usage_embed("!purge [lookback between 1 and 500]"))
            return

        deleted_count = await self._purge_victor_messages(
            ctx.channel,
            lookback=lookback,
            include_message_ids={ctx.message.id},
        )
        await ctx.send(embed=self._purge_complete_embed(deleted_count, lookback), delete_after=10)

    @app_commands.command(name="purge", description="Clear Victor's recent posts from this channel.")
    @app_commands.describe(lookback="How many recent messages to scan for Victor posts")
    @app_commands.guild_only()
    async def purge_messages_slash(
        self,
        interaction: discord.Interaction,
        lookback: app_commands.Range[int, 1, 500] = 100,
    ) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("/purge lookback"))
            return

        await self._defer_interaction(interaction, ephemeral=True)
        deleted_count = await self._purge_victor_messages(channel, lookback=lookback)
        await self._send_interaction_embed(
            interaction,
            self._purge_complete_embed(deleted_count, lookback),
            ephemeral=True,
        )

    @commands.command(name="sync")
    async def sync_commands(self, ctx: commands.Context) -> None:
        if not self._is_admin(ctx.author):
            embed = embeds.permission_denied_embed("Victor Admin")
            await ctx.send(embed=embed)
            return

        embed = await self._run_sync_action()
        await ctx.send(embed=embed)

    @app_commands.command(name="sync", description="Refresh Victor's slash command registry.")
    @app_commands.guild_only()
    async def sync_slash(self, interaction: discord.Interaction) -> None:
        await self.handle_console_sync_button(interaction)

    @commands.command(name="autosync")
    async def autosync_command(self, ctx: commands.Context, mode: Optional[str] = None) -> None:
        if not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Victor Admin"))
            return

        if not mode or mode.lower() not in {"on", "off"}:
            await ctx.send(embed=embeds.invalid_usage_embed("!autosync on|off"))
            return

        enable = mode.lower() == "on"
        self._set_auto_sync(enable)
        await ctx.send(embed=self._autosync_state_embed(enable))

    @app_commands.command(name="autosync", description="Toggle automatic slash sync on startup.")
    @app_commands.describe(mode="Set autosync on or off")
    @app_commands.guild_only()
    async def autosync_slash(self, interaction: discord.Interaction, mode: str) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return

        normalized = (mode or "").strip().lower()
        if normalized not in {"on", "off"}:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("/autosync on|off"))
            return

        enable = normalized == "on"
        self._set_auto_sync(enable)
        await self._send_interaction_embed(interaction, self._autosync_state_embed(enable), ephemeral=True)

    @commands.command(name="autoverifymode", aliases=["autoverifyflag"])
    async def autoverifymode_command(self, ctx: commands.Context, mode: Optional[str] = None) -> None:
        if not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Victor Admin"))
            return

        if not mode or mode.lower() not in {"on", "off"}:
            await ctx.send(embed=embeds.invalid_usage_embed("!autoverifymode on|off"))
            return

        enable = mode.lower() == "on"
        self._set_auto_verify(enable)
        await ctx.send(embed=self._autoverify_state_embed(enable))

    @app_commands.command(name="autoverifymode", description="Toggle Victor's auto-approval lane.")
    @app_commands.describe(mode="Set auto verify on or off")
    @app_commands.guild_only()
    async def autoverifymode_slash(self, interaction: discord.Interaction, mode: str) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return

        normalized = (mode or "").strip().lower()
        if normalized not in {"on", "off"}:
            await self._send_interaction_embed(interaction, embeds.invalid_usage_embed("/autoverifymode on|off"))
            return

        enable = normalized == "on"
        self._set_auto_verify(enable)
        await self._send_interaction_embed(interaction, self._autoverify_state_embed(enable), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(AdminCog(bot, cfg))
