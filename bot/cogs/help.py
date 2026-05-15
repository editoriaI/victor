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
        "Pick the lane you need and Victor will move you to the right place. Clean steps, quick answers, less wandering.",
        embeds.COLOR_NEUTRAL,
    )
    embed.add_field(
        name="[GET VERIFIED]",
        value=(
            f"Start in {verify_lane}. Send your Highrise username, wait for staff approval, and use the same lane later if you need to update your username."
        ),
        inline=False,
    )
    embed.add_field(
        name="[CHECK STATUS]",
        value="Open your status, view queue snapshots, or send a username update without guessing which command to use.",
        inline=False,
    )
    embed.add_field(
        name="[MARKETPLACE]",
        value="Browse listings, post what you are selling, or submit a wanted-item request through the member market board.",
        inline=False,
    )
    embed.add_field(
        name="[GOLD DESK]",
        value="E-bank access stays tight: `!balance` checks cIerk's Highrise wallet snapshot and `!transfer` queues a gold transfer.",
        inline=False,
    )
    embed.add_field(
        name="[STAFF TOOLS]",
        value="Manual review, sync, and auto modes still live here for staff without cluttering the member flow.",
        inline=False,
    )
    embed.add_field(
        name="[QUICK TIP]",
        value="If you are here as a member, most of what you need is Verify, Status, Marketplace, or Gold.",
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
        "trade": "blackmarket",
        "match": "blackmarket",
        "matches": "blackmarket",
        "request": "blackmarket",
        "accept": "blackmarket",
        "decline": "blackmarket",
        "cancel": "blackmarket",
        "cancelrequest": "blackmarket",
        "blackmarket": "blackmarket",
        "matchmaking": "blackmarket",
        "gold": "gold",
        "bank": "bank",
        "ebank": "bank",
        "balance": "bank",
        "transfer": "bank",
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
            "[ VERIFY START ]\nVictor only needs your exact Highrise username. Send it cleanly, let staff review it, and the rest of the record updates from there.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[START]", value="!verify (run inside the hr-id lane)", inline=False)
        embed.add_field(
            name="[HOW IT WORKS]",
            value="1. Open intake. 2. Send your Highrise username. 3. Staff reviews it. 4. Victor logs it or returns it for fixes.",
            inline=False,
        )
        embed.add_field(
            name="[AFTER THAT]",
            value="Watch for Victor's update. If something needs correcting, he will tell you what to fix instead of leaving you guessing.",
            inline=False,
        )
        embed.add_field(
            name="[USERNAME CHANGES]",
            value="If your Highrise name changes later, use `!updateusername NewName` or `/updateusername` in the same lane.",
            inline=False,
        )
        return embed

    if topic == "status":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // STATUS",
            "[ STATUS DESK ]\nCheck where your verification stands, whether your username is logged, and what still needs attention.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[CHECK]", value="!status | !status @user | use the menu Status button", inline=False)
        embed.add_field(
            name="[IF NOTHING IS ON FILE]",
            value="If Victor says there is no intake, rerun `!verify` in the hr-id lane and resend your username.",
            inline=False,
        )
        embed.add_field(
            name="[STAFF VIEW]",
            value="Staff can still use private status tools and queue snapshots without dumping that information into member chat.",
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
            "[ MARKET BOARD ]\nUse the market board to browse listings, post an item for sale, or submit a request for something you want to buy.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[SELLING]",
            value="!blackmarket list [query] | !blackmarket add \"item\" 25000 | !blackmarket remove <listing_id> | !vouches [@member] | !accept <match_id> | !decline <match_id>",
            inline=False,
        )
        embed.add_field(
            name="[BUYING]",
            value="!request \"item\" 25000 | !cancel <request_id>",
            inline=False,
        )
        embed.add_field(
            name="[SLASH COMMANDS]",
            value="/marketlist [query] | /marketadd item_name price | /marketremove listing_id | /vouches [member] | /request item_name max_price | /cancelrequest request_id | /accept match_id | /decline match_id",
            inline=False,
        )
        embed.add_field(
            name="[WHO CAN USE IT]",
            value="Anyone can browse. Selling needs the verified member role. Requests need the Buyer role. Accept or decline needs Seller or admin clearance.",
            inline=False,
        )
        return embed

    if topic == "gold":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // GOLD",
            "[ GOLD DESK ]\nGold market posts still route through the market board. E-bank actions stay limited to balance and transfer.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[FLOW]", value="Choose buy or sell, add the details, then Victor posts it to the right market lane.", inline=False)
        embed.add_field(
            name="[TRUSTED BOOST]",
            value="Trusted seller or buyer roles mirror the post into trusted market automatically.",
            inline=False,
        )
        embed.add_field(
            name="[WHO CAN USE IT]",
            value="Sell needs Seller clearance. Buy needs Buyer clearance. Admin still bypasses the gate.",
            inline=False,
        )
        return embed

    if topic == "bank":
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // EBANK",
            "[ EBANK ]\nVictor only exposes the two banking actions Discord needs: balance and transfer.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[BALANCE]", value="!balance | /balance", inline=False)
        embed.add_field(name="[TRANSFER]", value="!transfer <highrise_user_id> <amount> [note] | /transfer", inline=False)
        embed.add_field(
            name="[SOURCE]",
            value="cIerk reads the Highrise bot wallet with `get_wallet()` and sends gold with `tip_user()`.",
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
            "These features remain parked while the rest of the deck rebuilds. The trade flow is back online; restart still needs a cleaner pass.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[PARKED TEXT]", value="!restart", inline=False)
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

    return embeds.urgent_embed("HELP", "Unknown help topic. Try verify, status, blackmarket, gold, sync, admin, or parked.")


class SendNoteModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Member Note")
        self.help_cog = help_cog
        self.target_user = discord.ui.TextInput(label="Target Member mention or ID", placeholder="@member", required=True)
        self.note = discord.ui.TextInput(label="Note", style=discord.TextStyle.long, placeholder="What should Victor tell them?", required=True)
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


class MarketListingModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Post Listing")
        self.help_cog = help_cog
        self.item_name = discord.ui.TextInput(label="Item", placeholder="What are you selling?", required=True)
        self.price = discord.ui.TextInput(label="Price", placeholder="25000", required=True)
        self.add_item(self.item_name)
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        market_cog = interaction.client.get_cog("BlackmarketCog")
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the market file.", ephemeral=True)
            return
        await market_cog.handle_market_add_modal(interaction, str(self.item_name), str(self.price))


class RemoveListingModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Remove Listing")
        self.help_cog = help_cog
        self.listing_id = discord.ui.TextInput(label="Listing ID", placeholder="123", required=True)
        self.add_item(self.listing_id)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        market_cog = interaction.client.get_cog("BlackmarketCog")
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the market file.", ephemeral=True)
            return
        await market_cog.handle_market_remove_modal(interaction, str(self.listing_id))


class WantedItemModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Wanted Item")
        self.help_cog = help_cog
        self.item_name = discord.ui.TextInput(label="Item", placeholder="What are you trying to buy?", required=True)
        self.max_price = discord.ui.TextInput(label="Max Price", placeholder="25000", required=True)
        self.add_item(self.item_name)
        self.add_item(self.max_price)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        matchmaking_cog = interaction.client.get_cog("MatchmakingCog")
        if matchmaking_cog is None:
            await interaction.response.send_message("Victor misplaced the matchmaking file.", ephemeral=True)
            return
        await matchmaking_cog.handle_request_modal(interaction, str(self.item_name), str(self.max_price))


class GoldTradeModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog", action: str) -> None:
        normalized_action = "sell" if action.casefold() == "sell" else "buy"
        super().__init__(title=f"Victor // Gold {normalized_action.title()}")
        self.help_cog = help_cog
        self.action = normalized_action
        amount_prompt = "How much gold are you buying?" if normalized_action == "buy" else "How much gold are you selling?"
        self.amount = discord.ui.TextInput(label="Amount", placeholder=amount_prompt, required=True)
        self.rate_or_price = discord.ui.TextInput(
            label="Rate / Price",
            placeholder="User requested price or price calculated by rate",
            required=True,
        )
        self.payment_type = discord.ui.TextInput(
            label="Payment Type",
            placeholder="apple pay, cashapp, paypal, venmo, revolut, crypto, zelle, wise",
            default="cashapp, paypal",
            required=True,
        )
        self.transfer_type = discord.ui.TextInput(
            label="Transfer Type",
            placeholder="ebank, ebank only, trade, tip, trade/tip only",
            default="trade, tip",
            required=True,
        )
        self.notes = discord.ui.TextInput(
            label="Notes",
            style=discord.TextStyle.long,
            placeholder="Extra info, timing, limits, or anything the other side should know before messaging.",
            required=True,
            max_length=500,
        )
        self.add_item(self.amount)
        self.add_item(self.rate_or_price)
        self.add_item(self.payment_type)
        self.add_item(self.transfer_type)
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        market_cog = interaction.client.get_cog("BlackmarketCog")
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the gold desk.", ephemeral=True)
            return
        await market_cog.handle_gold_trade_modal(
            interaction,
            action=self.action,
            amount=str(self.amount),
            rate_or_price=str(self.rate_or_price),
            payment_type=str(self.payment_type),
            transfer_type=str(self.transfer_type),
            notes=str(self.notes),
        )


class ItemTradeModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog", action: str) -> None:
        normalized_action = "sell" if action.casefold() == "sell" else "buy"
        super().__init__(title=f"Victor // Item {normalized_action.title()}")
        self.help_cog = help_cog
        self.action = normalized_action
        prompt = "What item are you selling?" if normalized_action == "sell" else "What item are you looking for?"
        self.item_name = discord.ui.TextInput(label="Item", placeholder=prompt, required=True)
        self.price = discord.ui.TextInput(label="Price", placeholder="25000", required=True)
        self.details = discord.ui.TextInput(
            label="Details",
            style=discord.TextStyle.long,
            placeholder="Keep it clean: quantity, condition, timing, or anything someone should know.",
            required=True,
            max_length=500,
        )
        self.add_item(self.item_name)
        self.add_item(self.price)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        market_cog = interaction.client.get_cog("BlackmarketCog")
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the market file.", ephemeral=True)
            return
        await market_cog.handle_item_trade_modal(
            interaction,
            action=self.action,
            item_name=str(self.item_name),
            price_text=str(self.price),
            details=str(self.details),
        )


class PriceCheckModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Price Check")
        self.help_cog = help_cog
        self.item_name = discord.ui.TextInput(label="Item", placeholder="What needs a price check?", required=True)
        self.details = discord.ui.TextInput(
            label="Details",
            style=discord.TextStyle.long,
            placeholder="Add the version, rarity, quantity, or whatever context helps the board answer cleanly.",
            required=True,
            max_length=500,
        )
        self.add_item(self.item_name)
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        market_cog = interaction.client.get_cog("BlackmarketCog")
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the market file.", ephemeral=True)
            return
        await market_cog.handle_price_check_modal(
            interaction,
            item_name=str(self.item_name),
            details=str(self.details),
        )


class ProofOfSaleModal(discord.ui.Modal):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(title="Victor // Proof Of Selling")
        self.help_cog = help_cog
        self.details = discord.ui.TextInput(
            label="Proof / Vouch",
            style=discord.TextStyle.long,
            placeholder="Drop the quick summary, tags, and context that should go into the vouch lane.",
            required=True,
            max_length=500,
        )
        self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        market_cog = interaction.client.get_cog("BlackmarketCog")
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the market file.", ephemeral=True)
            return
        await market_cog.handle_proof_of_sale_modal(
            interaction,
            details=str(self.details),
        )


class MemberNoteQuickFixView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=86400)

    @discord.ui.button(label="Quick Fix", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def quick_fix(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = interaction.client.get_cog("VerifyCog")
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await verify_cog.handle_menu_update_username_button(interaction)


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


class StatusDeskView(discord.ui.View):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog

    async def _send_notice(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.send_message(text, ephemeral=True)

    def _verify_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("VerifyCog")

    @discord.ui.button(label="My Status", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def my_status(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await self._send_notice(interaction, "Victor misplaced the verification file.")
            return
        await verify_cog.handle_menu_status_button(interaction)

    @discord.ui.button(label="Queue Snapshot", style=discord.ButtonStyle.primary, emoji="📟")
    async def queue_snapshot(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await self._send_notice(interaction, "Victor misplaced the verification file.")
            return
        await verify_cog.handle_verify_queue_button(interaction)

    @discord.ui.button(label="Update Username", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def update_username(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await self._send_notice(interaction, "Victor misplaced the verification file.")
            return
        await verify_cog.handle_menu_update_username_button(interaction)

    @discord.ui.button(label="Admin Overview", style=discord.ButtonStyle.primary, emoji="📊")
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


class VerifyDeskView(discord.ui.View):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog

    async def _send_notice(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.send_message(text, ephemeral=True)

    def _verify_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("VerifyCog")

    @discord.ui.button(label="Open Intake", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def open_intake(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await self._send_notice(interaction, "Victor misplaced the verification file.")
            return
        await verify_cog.handle_menu_verify_button(interaction)

    @discord.ui.button(label="How It Works", style=discord.ButtonStyle.secondary, emoji="📋")
    async def how_it_works(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = build_help_topic_embed("verify")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MarketplaceDeskView(discord.ui.View):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog

    async def _send_notice(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="Open Board", style=discord.ButtonStyle.primary, emoji="💰")
    async def open_board(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            embed=self.help_cog._market_board_embed(),
            view=MarketBoardView(self.help_cog),
            ephemeral=True,
        )

    @discord.ui.button(label="How It Works", style=discord.ButtonStyle.secondary, emoji="📋")
    async def how_it_works(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = build_help_topic_embed("blackmarket")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MarketBoardView(discord.ui.View):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog

    async def _send_notice(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.send_message(text, ephemeral=True)

    def _market_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("BlackmarketCog")

    @discord.ui.button(label="Board Overview", style=discord.ButtonStyle.secondary, emoji="💰")
    async def board_overview(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(embed=self.help_cog._market_board_embed(), ephemeral=True)

    @discord.ui.button(label="Browse Listings", style=discord.ButtonStyle.secondary, emoji="📋")
    async def browse_listings(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await self._send_notice(interaction, "Victor misplaced the market file.")
            return
        await market_cog.handle_market_list_menu_button(interaction)

    @discord.ui.button(label="Post Listing", style=discord.ButtonStyle.secondary, emoji="🏷️")
    async def post_listing(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(MarketListingModal(self.help_cog))

    @discord.ui.button(label="Remove Listing", style=discord.ButtonStyle.secondary, emoji="🗑️")
    async def remove_listing(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RemoveListingModal(self.help_cog))

    @discord.ui.button(label="Sell Item", style=discord.ButtonStyle.primary, emoji="📌")
    async def sell_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ItemTradeModal(self.help_cog, "sell"))

    @discord.ui.button(label="Buy Item", style=discord.ButtonStyle.primary, emoji="🔎")
    async def buy_item(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ItemTradeModal(self.help_cog, "buy"))

    @discord.ui.button(label="Price Check", style=discord.ButtonStyle.secondary, emoji="🧾")
    async def price_check(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(PriceCheckModal(self.help_cog))

    @discord.ui.button(label="Proof / Vouch", style=discord.ButtonStyle.secondary, emoji="✅")
    async def proof_of_sale(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ProofOfSaleModal(self.help_cog))

    @discord.ui.button(label="Quick Repost", style=discord.ButtonStyle.secondary, emoji="♻️")
    async def quick_repost(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await self._send_notice(interaction, "Victor misplaced the market file.")
            return
        await market_cog.handle_repost_latest_market_post(interaction, asset_type="item")

    @discord.ui.button(label="Bump My Post", style=discord.ButtonStyle.secondary, emoji="📣")
    async def bump_post(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await self._send_notice(interaction, "Victor misplaced the market file.")
            return
        await market_cog.handle_bump_latest_market_post(interaction, asset_type="item")

    @discord.ui.button(label="Delete Latest Post", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_latest_post(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await self._send_notice(interaction, "Victor misplaced the market file.")
            return
        await market_cog.handle_remove_latest_market_post(interaction, asset_type="item")


class GoldBoardView(discord.ui.View):
    def __init__(self, help_cog: "HelpCog") -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog

    def _market_cog(self, interaction: discord.Interaction):
        return interaction.client.get_cog("BlackmarketCog")

    async def _send_gold_gate(self, interaction: discord.Interaction, action: str) -> None:
        author = interaction.user
        if not isinstance(author, discord.Member):
            await interaction.response.send_message("Victor needs a server member for the gold desk.", ephemeral=True)
            return
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the gold desk.", ephemeral=True)
            return
        trusted_roles = market_cog._trusted_roles(author)
        trusted_note = (
            "Trusted perks active: your sell post will hit market first, then mirror into trusted market after a short delay."
            if trusted_roles and action == "sell"
            else "Trusted perks active on this account."
            if trusted_roles
            else None
        )
        description = (
            "Gold buy posts route to looking for gold.\nGold sell posts route to market."
            if action == "buy"
            else "Gold sell posts route to market.\nTrusted sellers get a delayed mirror into trusted market."
        )
        embed = embeds.make_embed(
            f"{embeds.TITLE_BLACKMARKET} // GOLD CHECK",
            description,
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(name="[SCREENING]", value="trusted member confirmed" if trusted_roles else "standard member lane", inline=True)
        if trusted_note:
            embed.add_field(name="[TRUSTED PERKS]", value=trusted_note, inline=False)
        await interaction.response.send_message(
            embed=embed,
            view=GoldStartView(self.help_cog, action),
            ephemeral=True,
        )

    @discord.ui.button(label="Sell Gold", style=discord.ButtonStyle.primary, emoji="🥇")
    async def sell_gold(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_gold_gate(interaction, "sell")

    @discord.ui.button(label="Buy Gold", style=discord.ButtonStyle.secondary, emoji="💰")
    async def buy_gold(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._send_gold_gate(interaction, "buy")

    @discord.ui.button(label="How It Works", style=discord.ButtonStyle.secondary, emoji="📋")
    async def how_it_works(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = build_help_topic_embed("gold")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Quick Repost", style=discord.ButtonStyle.secondary, emoji="♻️")
    async def quick_repost(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the gold desk.", ephemeral=True)
            return
        await market_cog.handle_repost_latest_market_post(interaction, asset_type="gold")

    @discord.ui.button(label="Bump My Post", style=discord.ButtonStyle.secondary, emoji="📣")
    async def bump_post(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the gold desk.", ephemeral=True)
            return
        await market_cog.handle_bump_latest_market_post(interaction, asset_type="gold")

    @discord.ui.button(label="Delete Latest Post", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_latest_post(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        market_cog = self._market_cog(interaction)
        if market_cog is None:
            await interaction.response.send_message("Victor misplaced the gold desk.", ephemeral=True)
            return
        await market_cog.handle_remove_latest_market_post(interaction, asset_type="gold")


class GoldStartView(discord.ui.View):
    def __init__(self, help_cog: "HelpCog", action: str) -> None:
        super().__init__(timeout=180)
        self.help_cog = help_cog
        self.action = action

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.primary, emoji="➡️")
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(GoldTradeModal(self.help_cog, self.action))


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

    @discord.ui.button(label="Get Verified", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "Verify desk is open. Start intake when you're ready.",
            view=VerifyDeskView(self.help_cog),
            ephemeral=True,
        )

    @discord.ui.button(label="My Status", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "Status desk is open. Pick what you need.",
            view=StatusDeskView(self.help_cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Auto", style=discord.ButtonStyle.secondary, emoji="🧿")
    async def auto_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "Auto controls are open.",
            view=AutoModeSubMenu(self.help_cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Staff Manual", style=discord.ButtonStyle.secondary, emoji="📎")
    async def manual_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = self._verify_cog(interaction)
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await interaction.response.send_modal(ManualVerifyModal(self.help_cog))

    @discord.ui.button(label="Sync Desk", style=discord.ButtonStyle.secondary, emoji="📟")
    async def sync_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        admin_cog = self._admin_cog(interaction)
        if admin_cog is None:
            await interaction.response.send_message("Victor misplaced the admin desk.", ephemeral=True)
            return
        await admin_cog.handle_console_sync_button(interaction)

    @discord.ui.button(label="Marketplace", style=discord.ButtonStyle.secondary, emoji="💰")
    async def market_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "Marketplace desk is open. Browse the board or post when you're ready.",
            view=MarketplaceDeskView(self.help_cog),
            ephemeral=True,
        )

    @discord.ui.button(label="Gold Desk", style=discord.ButtonStyle.secondary, emoji="🥇")
    async def gold_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "Gold desk is open. Pick whether you're buying or selling and Victor will route it cleanly.",
            view=GoldBoardView(self.help_cog),
            ephemeral=True,
        )

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

    def _market_counts(self) -> dict[str, int]:
        conn = db.get_connection(self.cfg.db_path)
        try:
            listings_row = conn.execute("SELECT COUNT(*) AS count FROM listings WHERE status = 'OPEN'").fetchone()
            requests_row = conn.execute("SELECT COUNT(*) AS count FROM match_requests WHERE status = 'OPEN'").fetchone()
            matches_row = conn.execute("SELECT COUNT(*) AS count FROM matches WHERE status = 'PENDING'").fetchone()
        finally:
            conn.close()

        return {
            "listings": int(listings_row["count"]) if listings_row else 0,
            "requests": int(requests_row["count"]) if requests_row else 0,
            "pending_matches": int(matches_row["count"]) if matches_row else 0,
        }

    def _member_note_tips(self, note: str) -> list[str]:
        lowered = (note or "").casefold()
        tips: list[str] = []

        if any(token in lowered for token in ("username", "highrise", "hr", "verify", "verification", "bio")):
            tips.append("Use Quick Fix to reopen the username update flow without hunting for the command.")
        if "space" in lowered or "clean" in lowered or "exact" in lowered or "spelling" in lowered:
            tips.append("Send the exact Highrise username only, with no extra words or spacing.")
        if "bio" in lowered:
            tips.append("Double-check your Highrise bio before retrying if staff mentioned a bio mismatch.")
        if "price" in lowered or "market" in lowered or "gold" in lowered or "item" in lowered:
            tips.append("Keep the post short and specific so Victor can route it into the right market lane cleanly.")
        if "proof" in lowered or "vouch" in lowered:
            tips.append("Put sale proof and vouches in the proof lane so they do not get buried in market chat.")
        if not tips:
            tips.append("Read the note once, fix only the thing Victor called out, then retry cleanly.")
        return tips[:3]

    def _market_board_embed(self) -> discord.Embed:
        embed = embeds.make_embed(
            f"{embeds.TITLE_BLACKMARKET} // BOARD",
            "Market traffic runs through routed lanes now. Sell items to market, send item searches to lf items, and keep price checks and vouches in their own spots.",
            embeds.COLOR_NEUTRAL,
        )
        embed.add_field(
            name="[SELL ITEM]",
            value="Sell item posts route to the market lane. Trusted users also mirror into trusted market.",
            inline=False,
        )
        embed.add_field(
            name="[BUY ITEM]",
            value="Buy item posts route to lf items so requests stay readable for everyone.",
            inline=False,
        )
        embed.add_field(
            name="[PRICE CHECKS]",
            value="Price checks go straight to the dedicated price-check lane.",
            inline=False,
        )
        embed.add_field(
            name="[PROOF / VOUCH]",
            value="Proof of selling and vouches go to the proof lane instead of getting buried in market chatter.",
            inline=False,
        )
        return embed

    async def handle_send_note(
        self,
        interaction: discord.Interaction,
        target: str,
        note: str,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Victor needs a server context for that note.", ephemeral=True)
            return
        member = await self._resolve_member(interaction.guild, target)
        if member is None:
            await interaction.response.send_message("Victor could not find that member.", ephemeral=True)
            return
        embed = embeds.make_embed(
            f"{embeds.TITLE_HELP} // VICTOR NOTE",
            note,
            embeds.COLOR_NEUTRAL,
        )
        tips = self._member_note_tips(note)
        embed.add_field(name="[FROM]", value="Victor", inline=True)
        embed.add_field(name="[TARGET]", value=member.mention, inline=True)
        embed.add_field(name="[QUICK TIPS]", value="\n".join(f"- {tip}" for tip in tips), inline=False)
        embed.add_field(name="[NEXT]", value="Use Quick Fix if this note is asking for a verification or username correction.", inline=False)
        try:
            await member.send(embed=embed, view=MemberNoteQuickFixView())
        except discord.HTTPException:
            await interaction.response.send_message("Victor could not DM that member.", ephemeral=True)
            return
        await interaction.response.send_message("Victor delivered the note privately.", ephemeral=True)

    async def _resolve_member(self, guild: discord.Guild, raw_value: str) -> Optional[discord.Member]:
        cleaned = (raw_value or "").strip()
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        if not digits:
            return None
        member = guild.get_member(int(digits))
        if member is not None:
            return member
        try:
            return await guild.fetch_member(int(digits))
        except (discord.HTTPException, discord.Forbidden, discord.NotFound, ValueError):
            return None

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
