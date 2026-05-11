from __future__ import annotations

from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from bot import embeds
from bot.config import Config


class BankCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg

    def _endpoint(self, path: str) -> str:
        return f"{self.cfg.ivictor_bank_api_base_url}{path}"

    async def _get_balance(self) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(self._endpoint("/bank/balance")) as response:
                payload = await response.json()
                if response.status >= 400:
                    raise RuntimeError(str(payload.get("detail") or payload))
                return payload

    async def _queue_transfer(
        self,
        *,
        to_highrise_user_id: str,
        amount: int,
        requested_by: str,
        note: str,
    ) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._endpoint("/bank/transfer"),
                json={
                    "to_highrise_user_id": to_highrise_user_id,
                    "amount": amount,
                    "requested_by": requested_by,
                    "note": note,
                },
            ) as response:
                payload = await response.json()
                if response.status >= 400:
                    raise RuntimeError(str(payload.get("detail") or payload))
                return payload

    def _balance_embed(self, payload: dict) -> discord.Embed:
        embed = embeds.make_embed(
            f"{embeds.TITLE_ADMIN} // EBANK",
            "[ TREASURY BALANCE ]\n\nVictor checked iVictor's last Highrise wallet snapshot.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[GOLD]", value=f"{int(payload.get('gold') or 0):,}", inline=True)
        embed.add_field(name="[SOURCE]", value=str(payload.get("source") or "unknown"), inline=True)
        embed.add_field(name="[UPDATED]", value=str(payload.get("updated_at") or "not observed yet"), inline=False)
        return embed

    def _transfer_embed(self, payload: dict) -> discord.Embed:
        embed = embeds.make_embed(
            f"{embeds.TITLE_ADMIN} // EBANK",
            "[ TRANSFER QUEUED ]\n\niVictor will execute this through the Highrise bot wallet.",
            embeds.COLOR_OK,
        )
        embed.add_field(name="[ID]", value=str(payload.get("id") or "queued"), inline=True)
        embed.add_field(name="[TO]", value=str(payload.get("to_highrise_user_id") or "unknown"), inline=True)
        embed.add_field(name="[AMOUNT]", value=f"{int(payload.get('amount') or 0):,} gold", inline=True)
        embed.add_field(name="[STATUS]", value=str(payload.get("status") or "queued"), inline=True)
        return embed

    async def _send_error(self, target, message: str) -> None:
        embed = embeds.bank_transfer_error_embed(message)
        if isinstance(target, commands.Context):
            await target.send(embed=embed)
        elif target.response.is_done():
            await target.followup.send(embed=embed, ephemeral=True)
        else:
            await target.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="balance")
    async def balance_command(self, ctx: commands.Context) -> None:
        try:
            payload = await self._get_balance()
        except Exception as exc:
            await ctx.send(embed=embeds.bank_transfer_error_embed(f"iVictor bank API did not answer: {exc}"))
            return
        await ctx.send(embed=self._balance_embed(payload))

    @commands.command(name="transfer")
    async def transfer_command(
        self,
        ctx: commands.Context,
        to_highrise_user_id: Optional[str] = None,
        amount: Optional[int] = None,
        *,
        note: str = "discord-transfer",
    ) -> None:
        if not to_highrise_user_id or amount is None:
            await ctx.send(embed=embeds.invalid_usage_embed("!transfer <highrise_user_id> <amount> [note]"))
            return
        try:
            payload = await self._queue_transfer(
                to_highrise_user_id=to_highrise_user_id,
                amount=amount,
                requested_by=str(ctx.author.id),
                note=note,
            )
        except Exception as exc:
            await ctx.send(embed=embeds.bank_transfer_error_embed(f"Transfer was not queued: {exc}"))
            return
        await ctx.send(embed=self._transfer_embed(payload))

    @app_commands.command(name="balance", description="Check iVictor's Highrise gold wallet snapshot.")
    @app_commands.guild_only()
    async def balance_slash(self, interaction: discord.Interaction) -> None:
        try:
            payload = await self._get_balance()
        except Exception as exc:
            await self._send_error(interaction, f"iVictor bank API did not answer: {exc}")
            return
        await interaction.response.send_message(embed=self._balance_embed(payload), ephemeral=True)

    @app_commands.command(name="transfer", description="Queue a Highrise gold transfer through iVictor.")
    @app_commands.describe(
        to_highrise_user_id="Highrise user ID to receive the gold",
        amount="Gold amount to transfer",
        note="Optional receipt note",
    )
    @app_commands.guild_only()
    async def transfer_slash(
        self,
        interaction: discord.Interaction,
        to_highrise_user_id: str,
        amount: int,
        note: str = "discord-transfer",
    ) -> None:
        try:
            payload = await self._queue_transfer(
                to_highrise_user_id=to_highrise_user_id,
                amount=amount,
                requested_by=str(interaction.user.id),
                note=note,
            )
        except Exception as exc:
            await self._send_error(interaction, f"Transfer was not queued: {exc}")
            return
        await interaction.response.send_message(embed=self._transfer_embed(payload), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(BankCog(bot, cfg))
