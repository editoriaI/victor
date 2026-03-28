from typing import Callable, Optional

import discord
from discord.ext import commands

from bot import embeds
from bot.config import Config

HELP_OPTIONS = (
    ("verify", "🕯️ Verify", "Open intake and send the username to staff approval"),
    ("status", "🖤 Status", "Check where a verification thread currently stands"),
    ("manualverify", "📎 Manual Verify", "Finish a review case after the automated checks stall"),
    ("sync", "📟 Sync", "Refresh Victor's command registry"),
    ("parked", "🦇 Parked", "Features still waiting to come back online"),
)


def build_menu_embed() -> discord.Embed:
    embed = embeds.make_embed(
        f"{embeds.TITLE_HELP} // MENU",
        "Command board online. Press a lane and Victor executes the associated flow (or explains how staff can finish the lane).",
        embeds.COLOR_NEUTRAL,
    )
    embed.add_field(name="[LIVE TEXT]", value="!menu\n!help\n!verify\n!manualverify\n!status\n!sync\n!autoverify (staff only)", inline=False)
    embed.add_field(
        name="[HOW THIS BOARD WORKS]",
        value=(
            "verify launches intake.\n"
            "status pulls your current file.\n"
            "manual and parked open focused reference panels.\n"
            "sync fires only if the clicker has admin access."
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
            "verify opens an intake thread, collects a Highrise username, and sends it to staff for approval before logging.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value="!verify",
            inline=False,
        )
        embed.add_field(
            name="[FLOW]",
            value=(
                "phase 01: victor opens intake.\n"
                "phase 02: the member submits their HR username in the prompt.\n"
                "phase 03: victor posts it to staff with accept or reject buttons.\n"
                "phase 04: staff approval files it, updates nickname when possible, and closes the file."
            ),
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="run this in the server's hr-id lane. members can run their own intake there, staff signs off in the console, and manualverify still exists for corrections or overrides.",
            inline=False,
        )
        return embed

    if topic == "status":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // STATUS",
            "status shows whether your intake is pending, needs a retry, or has already been logged.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!status\n!status @user", inline=False)
        embed.add_field(
            name="[RETURNS]",
            value="status shows whether your intake is pending, needs a retry, or has already been logged.",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="use status in the hr-id lane. verifier or Victor Admin is required to inspect someone else.",
            inline=False,
        )
        return embed

    if topic == "manualverify":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // MANUAL",
            "manualverify allows staff to override, correct, or directly log a username.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!manualverify @user [username]", inline=False)
        embed.add_field(
            name="[WHEN TO USE IT]",
            value="use it when staff needs to correct a username on file, finish a stuck case, or override the intake manually.",
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
            "sync refreshes Victor's command registry when Discord starts acting unstable.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!sync", inline=False)
        embed.add_field(
            name="[WHEN TO USE IT]",
            value="after deploys, after command reloads, or when staff crash threads specifically tell you the command registry needs a refresh.",
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
                "`20xx` text command success\n"
                "`24xx` text command failure\n"
                "`90xx` staff crash thread\n"
                "`9101` verify manual review\n"
                "`9102` verify intake is waiting for staff approval"
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
        verify_cog = interaction.client.get_cog("VerifyCog")
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the intake clipboard.", ephemeral=True)
            return
        await verify_cog.handle_menu_verify_button(interaction)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = interaction.client.get_cog("VerifyCog")
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the file drawer.", ephemeral=True)
            return
        await verify_cog.handle_menu_status_button(interaction)

    @discord.ui.button(label="Manual", style=discord.ButtonStyle.secondary, emoji="📎")
    async def manual_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            embed=embeds.make_embed(
                f"{embeds.TITLE_HELP} // MANUAL",
                "Manual verify lets staff correct a username directly. Run `!manualverify @user username` in the verify lane when automated checks stall.",
                embeds.COLOR_NEUTRAL,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Sync", style=discord.ButtonStyle.secondary, emoji="📟")
    async def sync_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        admin_cog = interaction.client.get_cog("AdminCog")
        if admin_cog is None:
            await interaction.response.send_message("Victor misplaced the admin desk.", ephemeral=True)
            return
        await admin_cog.handle_console_sync_button(interaction)

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

async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(HelpCog(bot, cfg))
