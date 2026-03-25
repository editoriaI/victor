from typing import Callable, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import embeds
from bot.config import Config

HELP_OPTIONS = (
    ("verify", "Verify", "Issue code challenges and check verification status"),
    ("blackmarket", "Blackmarket", "Listings, prices, and seller access"),
    ("matchmaking", "Matchmaking", "Buyer requests and seller responses"),
    ("admin", "Admin", "Blacklist, sync, restart, and owner override"),
)


def build_help_topic_embed(feature: Optional[str]) -> discord.Embed:
    topic = (feature or "").strip().lower()
    aliases = {
        "market": "blackmarket",
        "bm": "blackmarket",
        "listings": "blackmarket",
        "marketlist": "blackmarket",
        "marketadd": "blackmarket",
        "marketremove": "blackmarket",
        "trade": "matchmaking",
        "match": "matchmaking",
        "matches": "matchmaking",
        "accept": "matchmaking",
        "decline": "matchmaking",
        "cancel": "matchmaking",
        "cancelrequest": "matchmaking",
        "mod": "admin",
        "sync": "admin",
        "restart": "admin",
        "manualverify": "verify",
        "owner": "admin",
    }
    topic = aliases.get(topic, topic)

    if not topic:
        return embeds.help_embed()

    if topic in {"verify", "status"}:
        embed = embeds.make_embed(
            "VICTOR // HELP // VERIFY",
            "Issue a code, tell the user to place it in their Highrise bio, then have them confirm with the button.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value="!verify @user username\n!manualverify @user [username]\n!status\n!status @user",
            inline=False,
        )
        embed.add_field(
            name="[SLASH]",
            value="/verify member highrise_username\n/manualverify member [highrise_username]\n/status [member]",
            inline=False,
        )
        embed.add_field(
            name="[FLOW]",
            value="First run: Victor confirms the Highrise username exists and issues a 4-character code. The user places it in their bio, then presses the `Confirm Bio Updated` button on Victor's message. Victor re-checks the API from that button. After two misses, staff can use manual verify.",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Verifier or Victor Admin is required for verification. The HBIC owner role bypasses this.",
            inline=False,
        )
        return embed

    if topic == "blackmarket":
        embed = embeds.make_embed(
            "VICTOR // HELP // BLACKMARKET",
            "Listings, pricing, and seller access.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value='!blackmarket list [query]\n!blackmarket add "item" 25000\n!blackmarket remove <listing_id>',
            inline=False,
        )
        embed.add_field(
            name="[SLASH]",
            value="/marketlist [query]\n/marketadd item_name price\n/marketremove listing_id",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Blackmarket or Victor Admin role is required to add or remove listings. The HBIC owner role bypasses this. List works for anyone not blacklisted.",
            inline=False,
        )
        return embed

    if topic in {"matchmaking", "request"}:
        embed = embeds.make_embed(
            "VICTOR // HELP // MATCH",
            "Buyer requests and seller responses.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value='!request "item" 25000\n!cancel <request_id>\n!accept <match_id>\n!decline <match_id>',
            inline=False,
        )
        embed.add_field(
            name="[SLASH]",
            value="/request item_name max_price\n/cancelrequest request_id\n/accept match_id\n/decline match_id",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Buyer role is required for requests. Seller role is required for accept and decline. The HBIC owner role bypasses both. Victor DMs matching sellers.",
            inline=False,
        )
        return embed

    if topic in {"admin", "blacklist"}:
        embed = embeds.make_embed(
            "VICTOR // HELP // ADMIN",
            "Restricted moderation controls.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value="!blacklist add @user reason\n!blacklist remove @user\n!blacklist list\n!sync\n!restart\n!manualverify @user [username]",
            inline=False,
        )
        embed.add_field(
            name="[SLASH]",
            value="/sync\n/restart\n/manualverify member [highrise_username]",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Victor Admin only. The HBIC owner role bypasses every role gate and blacklist restriction.",
            inline=False,
        )
        embed.add_field(
            name="[POST CODES]",
            value=(
                "`1001` child online\n"
                "`1101` restart requested\n"
                "`1102` restart complete\n"
                "`21xx` slash command success\n"
                "`25xx` slash command failure\n"
                "`20xx` text command success\n"
                "`24xx` text command failure\n"
                "`90xx` staff crash thread\n"
                "`9101` verify manual review"
            ),
            inline=False,
        )
        return embed

    embed = embeds.urgent_embed(
        "HELP",
        "Unknown help topic. Try verify, blackmarket, matchmaking, admin, sync, or restart.",
    )
    embed.add_field(name="[USAGE]", value="!help verify\n!help sync\n!help request", inline=False)
    return embed


class HelpTopicSelect(discord.ui.Select):
    def __init__(self, topic_builder: Callable[[Optional[str]], discord.Embed]) -> None:
        self.topic_builder = topic_builder
        options = [
            discord.SelectOption(label=label, value=value, description=description)
            for value, label, description in HELP_OPTIONS
        ]
        super().__init__(
            placeholder="Choose a help topic",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        embed = self.topic_builder(self.values[0])
        await interaction.response.send_message(embed=embed, ephemeral=True)


class HelpView(discord.ui.View):
    def __init__(self, topic_builder: Callable[[Optional[str]], discord.Embed]) -> None:
        super().__init__(timeout=180)
        self.topic_builder = topic_builder
        self.add_item(HelpTopicSelect(topic_builder))

    async def _send_topic(self, interaction: discord.Interaction, topic: str) -> None:
        embed = self.topic_builder(topic)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.secondary)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "verify")

    @discord.ui.button(label="Blackmarket", style=discord.ButtonStyle.secondary)
    async def blackmarket_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "blackmarket")

    @discord.ui.button(label="Matchmaking", style=discord.ButtonStyle.secondary)
    async def match_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "matchmaking")

    @discord.ui.button(label="Admin", style=discord.ButtonStyle.secondary)
    async def admin_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "admin")


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg

    def _topic_embed(self, feature: Optional[str]) -> discord.Embed:
        return build_help_topic_embed(feature)

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context, *, feature: Optional[str] = None) -> None:
        embed = self._topic_embed(feature)
        view = HelpView(self._topic_embed) if not feature else None
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="help", description="Show Victor help or a deeper feature guide.")
    @app_commands.describe(feature="Optional topic: verify, blackmarket, matchmaking, or admin")
    async def help_slash(self, interaction: discord.Interaction, feature: Optional[str] = None) -> None:
        embed = self._topic_embed(feature)
        view = HelpView(self._topic_embed) if not feature else None
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(HelpCog(bot, cfg))
