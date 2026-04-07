from typing import Callable, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot import db, embeds
from bot.config import Config
from bot.utils.permissions import has_any_role

HELP_OPTIONS = (
    ("verify", "🕯️ Verify", "Open intake and send the username to staff approval"),
    ("status", "🖤 Status", "Check where a verification thread currently stands"),
    ("manualverify", "📎 Manual Verify", "Finish a review case after the automated checks stall"),
    ("sync", "📟 Sync", "Refresh Victor's command registry"),
    ("autoverifymode", "🚚 Auto Verify", "Toggle Victor's auto-approval lane for intake threads"),
    ("parked", "🦇 Parked", "Features still waiting to come back online"),
)


def build_menu_embed(cfg: Config) -> discord.Embed:
    verify_lane = f"<#{cfg.verify_channel_id}>" if cfg.verify_channel_id else "the hr-id lane"
    embed = embeds.make_embed(
        f"{embeds.TITLE_HELP} // MENU",
        "Victor's console now feels like an X status, so every button is a pointer into the next plot point.",
        embeds.COLOR_NEUTRAL,
    )
    embed.add_field(
        name="[VERIFY QUEUE]",
        value=(
            f"Run `!verify` inside {verify_lane} to open the intake thread, drop your Highrise handle, "
            "then watch the console post the approval/rejection feed."
        ),
        inline=False,
    )
    embed.add_field(
        name="[STATUS DESK]",
        value="Tap Status to open a submenu with `!status`, the admin snapshot, and the Send Note modal.",
        inline=False,
    )
    embed.add_field(
        name="[AUTO MODES]",
        value="The Auto menu explains `!autoverifymode on|off` and `!autosync on|off` so Victor keeps pace.",
        inline=False,
    )
    embed.add_field(
        name="[PATCH & CONSOLE]",
        value="Victor posts updates to the console channel. Use Sync to resync slash commands, and keep the log clean.",
        inline=False,
    )
    return embed


def build_help_topic_embed(feature: Optional[str]) -> discord.Embed:
    topic = (feature or "").strip().lower()
    aliases = {
        "mod": "admin",
        "restart": "admin",
        "owner": "admin",
        "market": "blackmarket",
        "bm": "blackmarket",
        "listings": "blackmarket",
        "marketlist": "blackmarket",
        "marketadd": "blackmarket",
        "marketremove": "blackmarket",
        "trade": "parked",
        "match": "parked",
        "matches": "parked",
        "accept": "parked",
        "decline": "parked",
        "cancel": "parked",
        "cancelrequest": "parked",
        "blackmarket": "blackmarket",
        "matchmaking": "parked",
        "autoverify": "autoverifymode",
        "autosync": "autosync",
        "auto sync": "autosync",
    }
    topic = aliases.get(topic, topic)

    if not topic:
        return embeds.help_embed()

    if topic == "verify":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // VERIFY",
            "[ INTAKE THREAD OPENED ]\nStay still. Victor only needs your Highrise username. Keep it clean, keep it exact. "
            "This record is permanent. Staff will keep the console posted.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!verify (run inside the hr-id lane)", inline=False)
        embed.add_field(
            name="[FLOW]",
            value="1. Open intake. 2. Submit the Highrise handle. 3. Staff reviews the bio code. 4. Victor logs or returns it.",
            inline=False,
        )
        embed.add_field(
            name="[NOTES]",
            value="Wait for the console post, then add the code to your bio and hit the confirm button when ready.",
            inline=False,
        )
        return embed

    if topic == "status":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // STATUS",
            "[ STATUS: LOGGED ]\nMembers can check their own file. Staff can also scan only the users who already entered the verify flow to see who has been accepted and who still has not.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!status | !status @user | use the menu Status button", inline=False)
        embed.add_field(
            name="[GUIDANCE]",
            value="If Victor says 'No intake', rerun `!verify` inside the hr-id lane and resend the username.",
            inline=False,
        )
        embed.add_field(
            name="[ADMIN]",
            value="Staff menu/slash status stays private. Typed staff `!status` is sent by DM. Staff roster output uses names only and only includes users who already used verify.",
            inline=False,
        )
        return embed

    if topic == "manualverify":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // MANUAL",
            "[ MANUAL OVERRIDE ACCEPTED ]\nStaff can grab a user, correct the username, and seal the verification.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!manualverify @user username", inline=False)
        embed.add_field(
            name="[WHEN]",
            value="Use it when the automated checks keep failing or you have to nudge the intake forward.",
            inline=False,
        )
        return embed

    if topic == "sync":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // SYNC",
            "[ SYNC COMPLETE ✔ ]\nUse this if Discord hides slash commands or the menu misfires. Victor will refresh the tree.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!sync", inline=False)
        embed.add_field(name="[NOTES]", value="Victor Admin only. The menu Sync button runs this path for you.", inline=False)
        return embed

    if topic == "blackmarket":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // BLACKMARKET",
            "[ MARKET LANE LIVE ]\nVictor can browse, add, and remove blackmarket listings again while the rest of the trade deck stays staged.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[TEXT]",
            value="!blackmarket list [query] | !blackmarket add \"item\" 25000 | !blackmarket remove <listing_id>",
            inline=False,
        )
        embed.add_field(
            name="[SLASH]",
            value="/marketlist [query] | /marketadd item_name price | /marketremove listing_id",
            inline=False,
        )
        embed.add_field(
            name="[ACCESS]",
            value="Browsing stays read-only. Creating and removing listings now requires the verified Member role or admin clearance.",
            inline=False,
        )
        return embed

    if topic == "autosync":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // AUTO SYNC",
            "[ AUTO SYNC ENABLED ]\nVictor will automatically rerun `!sync` during startup when this is on.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!autosync on|off", inline=False)
        embed.add_field(
            name="[NOTES]",
            value="`on` resyncs the slash tree each time the bot boots. `off` keeps CTRL over the deploy.",
            inline=False,
        )
        return embed

    if topic == "autoverifymode":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // AUTO VERIFY",
            "[ AUTO VERIFY ENABLED ]\nToggle Victor's auto-approval gate so clean usernames skip staff review or not.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!autoverifymode on|off", inline=False)
        embed.add_field(
            name="[BEHAVIOR]",
            value="`on` lets Victor approve once the username passes the basic checklist. `off` keeps staff in the loop.",
            inline=False,
        )
        return embed

    if topic == "parked":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // PARKED",
            "These features remain parked while the rest of the deck rebuilds. Blackmarket is live again; matchmaking and restart still need a proper pass.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[PARKED TEXT]", value="!request | !cancel | !accept | !decline | !restart", inline=False)
        return embed

    if topic in {"admin", "blacklist"}:
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // ADMIN",
            "Restricted moderation utilities for staff.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TEXT]", value="!sync, !purge, !manualverify @user [username], !status @user", inline=False)
        embed.add_field(name="[NOTES]", value="HBIC owner bypasses every gate. Sync button re-syncs commands.", inline=False)
        return embed

    return embeds.urgent_embed("HELP", "Unknown help topic. Try verify, status, manualverify, sync, blackmarket, admin, or parked.")


class SendNoteModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Staff Note")
        self.help_cog = help_cog
        self.target_user = discord.ui.TextInput(label="Target Member mention or ID", placeholder="@member", required=True)
        self.note = discord.ui.TextInput(label="Note", style=discord.TextStyle.long, placeholder="What should Victor deliver to them?", required=True)
        self.add_item(self.target_user)
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.help_cog.handle_send_note(interaction, str(self.target_user), str(self.note))


class ManualVerifyModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Manual Verify")
        self.help_cog = help_cog
        self.target_user = discord.ui.TextInput(label="Target Member mention or ID", placeholder="@member", required=True)
        self.highrise_username = discord.ui.TextInput(label="Highrise username", placeholder="username", required=True)
        self.add_item(self.target_user)
        self.add_item(self.highrise_username)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.help_cog.handle_manual_verify_modal(
            interaction,
            str(self.target_user),
            str(self.highrise_username),
        )


class StatusSubMenu(discord.ui.View):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog

    async def _send_topic(self, interaction: discord.Interaction, topic: str) -> None:
        embed = build_help_topic_embed(topic)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _send_notice(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="Status Command", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def status_command(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "status")

    @discord.ui.button(label="Admin Overview", style=discord.ButtonStyle.primary, emoji="📟")
    async def admin_overview(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member) or not self.help_cog._is_admin_member(author):
            await self._send_notice(interaction, "You do not have clearance for the admin snapshot.")
            return
        counts = self.help_cog._verification_counts()
        embed = embeds.make_embed(
            f"{embeds.TITLE_ADMIN} // STATUS OVERVIEW",
            "Current verification snapshot.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[VERIFIED]", value=str(counts["verified"]), inline=True)
        embed.add_field(name="[PENDING]", value=str(counts["pending"]), inline=True)
        embed.add_field(name="[REJECTED]", value=str(counts["rejected"]), inline=True)
        embed.add_field(name="[OTHER]", value=str(counts["other"]), inline=True)
        embed.add_field(name="[TOTAL]", value=str(counts["total"]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Send Note", style=discord.ButtonStyle.secondary, emoji="📗")
    async def send_note(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(SendNoteModal(self.help_cog))


class AutoModeSubMenu(discord.ui.View):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog

    def _admin_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("AdminCog")

    @discord.ui.button(label="Auto Verify", style=discord.ButtonStyle.secondary, emoji="🧿")
    async def auto_verify(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        admin_cog = self._admin_cog(interaction)
        if admin_cog is None:
            await interaction.response.send_message("Victor misplaced the admin desk.", ephemeral=True)
            return
        await admin_cog.handle_auto_verify_toggle(interaction, not admin_cog._is_auto_verify_enabled())

    @discord.ui.button(label="Auto Sync", style=discord.ButtonStyle.secondary, emoji="🛰️")
    async def auto_sync(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        admin_cog = self._admin_cog(interaction)
        if admin_cog is None:
            await interaction.response.send_message("Victor misplaced the admin desk.", ephemeral=True)
            return
        await admin_cog.handle_auto_sync_toggle(interaction, not admin_cog._is_auto_sync_enabled())


class MenuView(discord.ui.View):
    def __init__(self, topic_builder: Callable[[Optional[str]], discord.Embed], help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.topic_builder = topic_builder
        self.help_cog = help_cog

    async def _send_topic(self, interaction: discord.Interaction, topic: str) -> None:
        embed = self.topic_builder(topic)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _verify_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("VerifyCog")

    def _admin_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("AdminCog")

    def _market_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("BlackmarketCog")

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await verify_cog.handle_menu_verify_button(interaction)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await verify_cog.handle_menu_status_button(interaction)

    @discord.ui.button(label="Auto Modes", style=discord.ButtonStyle.secondary, emoji="🧿")
    async def auto_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "Auto toggles to keep Victor leaning into the correct flow.",
            view=AutoModeSubMenu(self.help_cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Manual", style=discord.ButtonStyle.secondary, emoji="📎")
    async def manual_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await interaction.response.send_modal(ManualVerifyModal(self.help_cog))

    @discord.ui.button(label="Sync", style=discord.ButtonStyle.secondary, emoji="📟")
    async def sync_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        admin_cog = self._admin_cog(interaction)
        if admin_cog is None:
            await interaction.response.send_message("Victor misplaced the admin desk.", ephemeral=True)
            return
        await admin_cog.handle_console_sync_button(interaction)

    @discord.ui.button(label="Market", style=discord.ButtonStyle.secondary, emoji="💰")
    async def market_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the market file.", ephemeral=True)
            return
        await market_cog.handle_market_list_menu_button(interaction)

    @discord.ui.button(label="Parked", style=discord.ButtonStyle.secondary, emoji="🦇")
    async def parked_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_topic(interaction, "parked")


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot, cfg: Config) -> None:
        self.bot = bot
        self.cfg = cfg

    def _is_admin_member(self, member: discord.Member) -> bool:
        if has_any_role(member, self.cfg.roles.get("owner", [])):
            return True
        return has_any_role(member, self.cfg.roles.get("admin", []))

    def _verification_counts(self) -> dict[str, int]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            rows = conn.execute(
                "SELECT UPPER(status) AS status, COUNT(*) AS count FROM verification_codes GROUP BY status"
            ).fetchall()
        finally:
            conn.close()
        total = sum(row["count"] for row in rows)
        counts = {row["status"]: row["count"] for row in rows}
        verified = sum(counts.get(status, 0) for status in ("VERIFIED", "USERNAME LOGGED", "LOGGED"))
        pending = counts.get("PENDING", 0)
        rejected = counts.get("REJECTED", 0)
        other = total - verified - pending - rejected
        return {"verified": verified, "pending": pending, "rejected": rejected, "other": max(other, 0), "total": total}

    async def handle_send_note(
        self,
        interaction: discord.Interaction,
        target: str,
        note: str,
    ) -> None:
        embed = embeds.make_embed(
            f"{embeds.TITLE_ADMIN} // STAFF NOTE",
            note,
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[TARGET]", value=target, inline=True)
        embed.add_field(name="[AUTHOR]", value=interaction.user.mention, inline=True)
        channel_id = self.cfg.verify_channel_id or self.cfg.log_channel_id
        if channel_id:
            channel = interaction.client.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await interaction.client.fetch_channel(channel_id)
                except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                    channel = None
            if channel:
                await channel.send(embed=embed)
        await interaction.response.send_message("Note posted.", ephemeral=True)

    async def handle_manual_verify_modal(
        self,
        interaction: discord.Interaction,
        target: str,
        highrise_username: str,
    ) -> None:
        verify_cog = interaction.client.get_cog("VerifyCog")
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await verify_cog.handle_manual_verify_request(
            interaction,
            target,
            highrise_username,
            source="menu_manual",
        )

    def _topic_embed(self, feature: Optional[str]) -> discord.Embed:
        return build_help_topic_embed(feature)

    def _menu_embed(self) -> discord.Embed:
        return build_menu_embed(self.cfg)

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context, *, feature: Optional[str] = None) -> None:
        embed = self._topic_embed(feature)
        await ctx.send(embed=embed)

    @commands.command(name="menu")
    async def menu_command(self, ctx: commands.Context) -> None:
        await ctx.send(embed=self._menu_embed(), view=MenuView(self._topic_embed, self))

    @app_commands.command(name="help", description="Open Victor's help desk for the live lanes.")
    @app_commands.describe(feature="Optional topic like verify, status, sync, or blackmarket")
    @app_commands.guild_only()
    async def help_slash(self, interaction: discord.Interaction, feature: Optional[str] = None) -> None:
        await interaction.response.send_message(embed=self._topic_embed(feature), ephemeral=True)

    @app_commands.command(name="menu", description="Open Victor's command board.")
    @app_commands.guild_only()
    async def menu_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=self._menu_embed(),
            view=MenuView(self._topic_embed, self),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    cfg = bot.victor_config
    await bot.add_cog(HelpCog(bot, cfg))
