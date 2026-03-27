from typing import Callable, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import embeds
from bot.config import Config

HELP_OPTIONS = (
    ("verify", "🕯️ Verify", "Issue code challenges and check verification status"),
    ("status", "🖤 Status", "Check where a verification thread currently stands"),
    ("manualverify", "📎 Manual Verify", "Finish a review case after the automated checks stall"),
    ("sync", "📟 Sync", "Resync Victor's slash tree with Discord"),
    ("parked", "🦇 Parked", "Features still waiting to come back online"),
)


def build_menu_embed() -> discord.Embed:
    embed = embeds.make_embed(
        f"{embeds.TITLE_HELP} // MENU",
        "command board loaded. tap a lane below and victor will open the matching panel in the ui.",
        embeds.COLOR_NEUTRAL,
    )
    embed.add_field(name="[LIVE TEXT]", value="!menu\n!help\n!verify\n!manualverify\n!status\n!sync", inline=False)
    embed.add_field(name="[LIVE SLASH]", value="/menu\n/help\n/verify\n/manualverify\n/status\n/sync", inline=False)
    embed.add_field(
        name="[HOW THIS BOARD WORKS]",
        value=(
            "each button opens a focused embed for that command.\n"
            "commands that need arguments still show their exact usage before you run them."
        ),
        inline=False,
    )
    embed.add_field(
        name="[BACKSTAGE]",
        value="blackmarket, matchmaking, and restart are still parked until we bring them back properly.",
        inline=False,
    )
    return embed


def build_help_topic_embed(feature: Optional[str]) -> discord.Embed:
    topic = (feature or "").strip().lower()
    aliases = {
        "mod": "admin",
        "restart": "admin",
        "owner": "admin",
        "market": "parked",
        "bm": "parked",
        "listings": "parked",
        "marketlist": "parked",
        "marketadd": "parked",
        "marketremove": "parked",
        "trade": "parked",
        "match": "parked",
        "matches": "parked",
        "accept": "parked",
        "decline": "parked",
        "cancel": "parked",
        "cancelrequest": "parked",
        "blackmarket": "parked",
        "matchmaking": "parked",
    }
    topic = aliases.get(topic, topic)

    if not topic:
        return embeds.help_embed()

    if topic == "verify":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // VERIFY",
            "issue the code thread, send the user to their bio, then make them prove they updated it.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value="!verify @user username",
            inline=False,
        )
        embed.add_field(
            name="[SLASH]",
            value="/verify member highrise_username",
            inline=False,
        )
        embed.add_field(
            name="[FLOW]",
            value=(
                "phase 01: victor validates the Highrise username and issues a code.\n"
                "phase 02: the user updates the bio and hits the recheck button.\n"
                "phase 03: if they keep missing, the case escalates to manual review."
            ),
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Verifier or Victor Admin is required for verification. The HBIC owner role bypasses this.",
            inline=False,
        )
        return embed

    if topic == "status":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // STATUS",
            "pull the current verification thread and see exactly where the ritual is stuck.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!status\n!status @user", inline=False)
        embed.add_field(name="[SLASH]", value="/status [member]", inline=False)
        embed.add_field(
            name="[RETURNS]",
            value="verified state, linked Highrise username, pending code if one exists, and the current fail count.",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="members can inspect themselves. verifier or Victor Admin is required to inspect someone else.",
            inline=False,
        )
        return embed

    if topic == "manualverify":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // MANUAL",
            "use this when a verify case has landed on the staff desk and a human needs to stamp it through.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!manualverify @user [username]", inline=False)
        embed.add_field(name="[SLASH]", value="/manualverify member [highrise_username]", inline=False)
        embed.add_field(
            name="[WHEN TO USE IT]",
            value="only after the automated verify checks have pushed the case into manual review, unless you intentionally provide a username override.",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Verifier or Victor Admin only. use the staff thread receipts before you stamp a pass.",
            inline=False,
        )
        return embed

    if topic == "sync":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // SYNC",
            "this is the command-tree reset. use it when discord's slash state starts acting stale or confused.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!sync", inline=False)
        embed.add_field(name="[SLASH]", value="/sync", inline=False)
        embed.add_field(
            name="[WHEN TO USE IT]",
            value="after deploys, after command reloads, or when staff crash threads specifically tell you the slash tree needs a resync.",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Victor Admin only. this does not re-enable parked features by itself.",
            inline=False,
        )
        return embed

    if topic == "parked":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // PARKED",
            "these features are still offstage while victor comes back online in pieces.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[PARKED TEXT]",
            value=(
                '!blackmarket list [query]\n'
                '!blackmarket add "item" 25000\n'
                '!blackmarket remove <listing_id>\n'
                '!request "item" 25000\n'
                '!cancel <request_id>\n'
                '!accept <match_id>\n'
                '!decline <match_id>'
            ),
            inline=False,
        )
        embed.add_field(
            name="[PARKED SLASH]",
            value=(
                "/marketlist [query]\n"
                "/marketadd item_name price\n"
                "/marketremove listing_id\n"
                "/request item_name max_price\n"
                "/cancelrequest request_id\n"
                "/accept match_id\n"
                "/decline match_id"
            ),
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="help can document them, but victor cannot run them live yet. verify and admin are the active lanes right now.",
            inline=False,
        )
        return embed

    if topic in {"admin", "blacklist"}:
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // ADMIN",
            "restricted moderation controls and recovery tools.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value="!sync\n!manualverify @user [username]\n!status @user",
            inline=False,
        )
        embed.add_field(
            name="[SLASH]",
            value="/sync\n/manualverify member [highrise_username]\n/status [member]",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Victor Admin handles sync. Verifier or Victor Admin can finish a manual verify. The HBIC owner role bypasses every role gate.",
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
        "Unknown help topic. Try verify, status, manualverify, sync, admin, or parked.",
    )
    embed.add_field(
        name="[USAGE]",
        value="!help verify\n!help status\n!help manualverify\n!help sync\n!help parked",
        inline=False,
    )
    return embed


class HelpTopicSelect(discord.ui.Select):
    def __init__(self, topic_builder: Callable[[Optional[str]], discord.Embed]) -> None:
        self.topic_builder = topic_builder
        options = [
            discord.SelectOption(label=label, value=value, description=description)
            for value, label, description in HELP_OPTIONS
        ]
        super().__init__(
            placeholder="pick a thread to open",
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

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.secondary, emoji="🕯️")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "verify")

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "status")

    @discord.ui.button(label="Manual", style=discord.ButtonStyle.secondary, emoji="📎")
    async def manual_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "manualverify")

    @discord.ui.button(label="Sync", style=discord.ButtonStyle.secondary, emoji="📟")
    async def sync_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "sync")

    @discord.ui.button(label="Parked", style=discord.ButtonStyle.secondary, emoji="🦇")
    async def parked_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "parked")


class MenuView(discord.ui.View):
    def __init__(self, topic_builder: Callable[[Optional[str]], discord.Embed]) -> None:
        super().__init__(timeout=180)
        self.topic_builder = topic_builder

    async def _send_panel(self, interaction: discord.Interaction, topic: str) -> None:
        await interaction.response.send_message(embed=self.topic_builder(topic), ephemeral=True)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.secondary, emoji="🕯️")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_panel(interaction, "verify")

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_panel(interaction, "status")

    @discord.ui.button(label="Manual", style=discord.ButtonStyle.secondary, emoji="📎")
    async def manual_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_panel(interaction, "manualverify")

    @discord.ui.button(label="Sync", style=discord.ButtonStyle.secondary, emoji="📟")
    async def sync_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_panel(interaction, "sync")

    @discord.ui.button(label="Parked", style=discord.ButtonStyle.secondary, emoji="🦇")
    async def parked_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_panel(interaction, "parked")


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg

    def _topic_embed(self, feature: Optional[str]) -> discord.Embed:
        return build_help_topic_embed(feature)

    def _menu_embed(self) -> discord.Embed:
        return build_menu_embed()

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context, *, feature: Optional[str] = None) -> None:
        embed = self._topic_embed(feature)
        view = HelpView(self._topic_embed) if not feature else None
        await ctx.send(embed=embed, view=view)

    @commands.command(name="menu")
    async def menu_command(self, ctx: commands.Context) -> None:
        await ctx.send(embed=self._menu_embed(), view=MenuView(self._topic_embed))

    @app_commands.command(name="help", description="Show Victor help or a deeper feature guide.")
    @app_commands.describe(feature="Optional topic: verify, status, manualverify, sync, or parked")
    async def help_slash(self, interaction: discord.Interaction, feature: Optional[str] = None) -> None:
        embed = self._topic_embed(feature)
        view = HelpView(self._topic_embed) if not feature else None
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="menu", description="Open Victor's live command board.")
    async def menu_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=self._menu_embed(), view=MenuView(self._topic_embed), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(HelpCog(bot, cfg))
