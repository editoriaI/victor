from typing import Optional

AUTO_SYNC_FLAG = "autosync"
AUTO_VERIFY_FLAG = "autoverify"

import discord
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

    async def handle_console_sync_button(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return
        await self._defer_interaction(interaction, ephemeral=True)
        embed = await self._run_sync_action()
        await self._send_interaction_embed(interaction, embed)

    @commands.command(name="sync")
    async def sync_commands(self, ctx: commands.Context) -> None:
        if not self._is_admin(ctx.author):
            embed = embeds.permission_denied_embed("Victor Admin")
            await ctx.send(embed=embed)
            return

        embed = await self._run_sync_action()
        await ctx.send(embed=embed)

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
        state_text = "ENABLED" if enable else "DISABLED"
        embed = embeds.make_embed(
            embeds.TITLE_ADMIN,
            f"[ AUTO SYNC {state_text} ]\n\nVictor will now {'run' if enable else 'skip'} an automatic sync on startup.",
            embeds.COLOR_OK if enable else embeds.COLOR_WARN,
        )
        embed.add_field(name="[STATE]", value=state_text, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="autoverifymode", aliases=["autoverifyflag"])
    async def autoverify_command(self, ctx: commands.Context, mode: Optional[str] = None) -> None:
        if not self._is_admin(ctx.author):
            await ctx.send(embed=embeds.permission_denied_embed("Victor Admin"))
            return

        if not mode or mode.lower() not in {"on", "off"}:
            await ctx.send(embed=embeds.invalid_usage_embed("!autoverifymode on|off"))
            return

        enable = mode.lower() == "on"
        self._set_auto_verify(enable)
        state_text = "ENABLED" if enable else "DISABLED"
        embed = embeds.make_embed(
            embeds.TITLE_ADMIN,
            f"[ AUTO VERIFY {state_text} ]\n\nVictor will now {'auto-approve' if enable else 'require'} intake submissions.",
            embeds.COLOR_OK if enable else embeds.COLOR_WARN,
        )
        embed.add_field(name="[STATE]", value=state_text, inline=True)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(AdminCog(bot, cfg))
