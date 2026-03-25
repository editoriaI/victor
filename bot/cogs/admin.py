import asyncio
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import db
from bot import embeds
from bot.config import Config
from bot.utils.command_logging import log_system_event
from bot.utils.permissions import has_any_role
from bot.utils.restart_notice import write_restart_notice


class AdminCog(commands.Cog):
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

    async def _send_interaction_embed(
        self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = True
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    async def _run_sync_action(self) -> discord.Embed:
        synced = await self.bot.tree.sync()
        embed = embeds.make_embed(
            "VICTOR // ADMIN",
            "Slash commands resynced. Bureaucracy survives.",
            embeds.COLOR_OK,
        )
        embed.add_field(name="[SYNCED]", value=str(len(synced)), inline=True)
        return embed

    async def _queue_restart(self, actor_id: int, guild_id: Optional[int], surface: str) -> discord.Embed:
        self.bot.victor_restart_requested = True
        write_restart_notice(actor_id, guild_id, surface)
        logging.getLogger("victor.system").info(
            "Restart requested | surface=%s | actor=%s | guild=%s",
            surface,
            actor_id,
            guild_id if guild_id else "dm",
        )
        await log_system_event(
            self.bot,
            self.cfg,
            "Restart Requested",
            details=f"actor={actor_id} | guild={guild_id if guild_id else 'dm'} | surface={surface}",
        )
        embed = embeds.make_embed(
            "VICTOR // ADMIN",
            "Restart requested. Hold your nerve.",
            embeds.COLOR_WARN,
        )
        asyncio.create_task(self._restart_after_notice())
        return embed

    async def _restart_after_notice(self, delay: float = 1.5) -> None:
        logging.getLogger("victor.system").info(
            "Restart countdown started | delay=%.1fs | child=%s",
            delay,
            getattr(self.bot.user, "name", "unknown"),
        )
        await asyncio.sleep(delay)
        logging.getLogger("victor.system").info("Restart countdown finished | closing bot client")
        await self.bot.close()

    async def handle_console_sync_button(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return
        embed = await self._run_sync_action()
        await self._send_interaction_embed(interaction, embed)

    async def handle_console_restart_button(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return
        embed = await self._queue_restart(author.id, interaction.guild_id, "console")
        await self._send_interaction_embed(interaction, embed)

    @commands.group(name="blacklist", invoke_without_command=True)
    async def blacklist(self, ctx: commands.Context) -> None:
        embed = embeds.invalid_usage_embed("!blacklist add | remove | list")
        await ctx.send(embed=embed)

    @blacklist.command(name="add")
    async def blacklist_add(self, ctx: commands.Context, member: discord.Member, *, reason: str = "") -> None:
        if not self._is_admin(ctx.author):
            embed = embeds.permission_denied_embed("Victor Admin")
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            db.add_blacklist(conn, str(member.id), reason or "Unspecified")
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="BLACKLIST_ADD",
                target_id=str(member.id),
                details=reason or "Unspecified",
            )
            conn.commit()
        finally:
            conn.close()

        embed = embeds.blacklist_added_embed(member.mention)
        await ctx.send(embed=embed)

    @blacklist.command(name="remove")
    async def blacklist_remove(self, ctx: commands.Context, member: discord.Member) -> None:
        if not self._is_admin(ctx.author):
            embed = embeds.permission_denied_embed("Victor Admin")
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            db.remove_blacklist(conn, str(member.id))
            db.log_audit(
                conn,
                actor_id=str(ctx.author.id),
                action="BLACKLIST_REMOVE",
                target_id=str(member.id),
                details="removed",
            )
            conn.commit()
        finally:
            conn.close()

        embed = embeds.blacklist_removed_embed(member.mention)
        await ctx.send(embed=embed)

    @blacklist.command(name="list")
    async def blacklist_list(self, ctx: commands.Context) -> None:
        if not self._is_admin(ctx.author):
            embed = embeds.permission_denied_embed("Victor Admin")
            await ctx.send(embed=embed)
            return

        conn = db.get_connection(self.cfg.db_path)
        try:
            entries = db.list_blacklist(conn)
        finally:
            conn.close()

        embed = embeds.blacklist_list_embed(entries)
        await ctx.send(embed=embed)

    @commands.command(name="sync")
    async def sync_commands(self, ctx: commands.Context) -> None:
        if not self._is_admin(ctx.author):
            embed = embeds.permission_denied_embed("Victor Admin")
            await ctx.send(embed=embed)
            return

        embed = await self._run_sync_action()
        await ctx.send(embed=embed)

    @commands.command(name="restart")
    async def restart_bot(self, ctx: commands.Context) -> None:
        if not self._is_admin(ctx.author):
            embed = embeds.permission_denied_embed("Victor Admin")
            await ctx.send(embed=embed)
            return

        embed = await self._queue_restart(ctx.author.id, ctx.guild.id if ctx.guild else None, "prefix")
        await ctx.send(embed=embed)

    @app_commands.command(name="sync", description="Resync Victor's slash commands with Discord.")
    @app_commands.guild_only()
    async def sync_slash(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return

        embed = await self._run_sync_action()
        await self._send_interaction_embed(interaction, embed)

    @app_commands.command(name="restart", description="Restart Victor through the supervisor.")
    @app_commands.guild_only()
    async def restart_slash(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return

        embed = await self._queue_restart(author.id, interaction.guild_id, "slash")
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(AdminCog(bot, cfg))
