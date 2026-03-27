from typing import Optional

import discord
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
        return embeds.sync_success_embed(len(synced))

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

async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(AdminCog(bot, cfg))
