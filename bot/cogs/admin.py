from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import embeds
from bot.config import Config
from bot.utils.permissions import has_any_role


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
            embeds.TITLE_ADMIN,
            "Slash commands resynced. Verify is back on the board and the rest can wait their turn.",
            embeds.COLOR_OK,
        )
        embed.add_field(name="[SYNCED]", value=str(len(synced)), inline=True)
        return embed

    async def handle_console_sync_button(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return
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

    @app_commands.command(name="sync", description="Resync Victor's slash commands with Discord.")
    @app_commands.guild_only()
    async def sync_slash(self, interaction: discord.Interaction) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self._is_admin(author):
            await self._send_interaction_embed(interaction, embeds.permission_denied_embed("Victor Admin"))
            return

        embed = await self._run_sync_action()
        await self._send_interaction_embed(interaction, embed)


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(AdminCog(bot, cfg))
