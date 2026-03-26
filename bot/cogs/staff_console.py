from typing import Optional, Tuple

import discord
from discord.ext import commands

from bot.config import Config
from bot.utils.command_logging import send_log_channel

COMMAND_ACTION_VIEW_ID = "victor:console:command"
VERIFY_REVIEW_VIEW_ID = "victor:console:verify_review"

STAFF_COMMAND_CODES = {
    "verify": 9011,
    "manualverify": 9012,
    "status": 9013,
    "help": 9014,
    "restart": 9015,
    "sync": 9016,
    "blacklist": 9017,
    "blackmarket": 9018,
    "marketlist": 9019,
    "marketadd": 9020,
    "marketremove": 9021,
    "request": 9022,
    "cancel": 9023,
    "cancelrequest": 9024,
    "accept": 9025,
    "decline": 9026,
    "unknown": 9099,
}


def _field_value(embed: discord.Embed, name: str) -> Optional[str]:
    for field in embed.fields:
        if field.name == name:
            return field.value
    return None


def _staff_code(issue: Optional[str], *, command_name: Optional[str] = None) -> int:
    if issue == "Manual verification review":
        return 9101
    if issue == "Command failure":
        return STAFF_COMMAND_CODES.get((command_name or "").casefold(), STAFF_COMMAND_CODES["unknown"])
    return 9999


def build_staff_attention_embed(
    title: str,
    description: str,
    *,
    color: int = 0xB22222,
    tagged_user_id: Optional[int] = None,
    issue: Optional[str] = None,
    location: Optional[str] = None,
    details: Optional[str] = None,
    highrise_username: Optional[str] = None,
    stage: Optional[str] = None,
    outcome: Optional[str] = None,
    next_move: Optional[str] = None,
    quick_fix: Optional[str] = None,
    apply_fix: Optional[str] = None,
    code: Optional[str] = None,
    bio_preview: Optional[str] = None,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_author(name="🕸️ @victor.intern opened a staff thread")
    embed.set_footer(text="v i c t o r . s o c i a l // staff desk")

    if code:
        embed.add_field(name="Code", value=code, inline=True)

    if issue:
        embed.add_field(name="Issue", value=issue, inline=False)
    if tagged_user_id is not None:
        embed.add_field(name="[USER]", value=f"<@{tagged_user_id}>", inline=True)
    if highrise_username:
        embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    if location:
        embed.add_field(name="Where", value=location, inline=True)
    if stage:
        embed.add_field(name="Stage", value=stage, inline=True)
    if outcome:
        embed.add_field(name="Status", value=outcome, inline=True)
    if details:
        embed.add_field(name="Receipts", value=details[:1024], inline=False)
    if bio_preview:
        embed.add_field(name="Bio Preview", value=bio_preview[:1024], inline=False)
    if next_move:
        embed.add_field(name="Desk Note", value=next_move[:1024], inline=False)
    if quick_fix:
        embed.add_field(name="Quick Fix", value=quick_fix[:1024], inline=False)
    if apply_fix:
        embed.add_field(name="Apply Fix", value=apply_fix[:1024], inline=False)
    return embed


def infer_command_fix(command_name: str, details: Optional[str]) -> Tuple[str, Optional[str]]:
    lowered = (details or "").casefold()
    command_name = (command_name or "").casefold()

    if "unknown interaction" in lowered or "notfound" in lowered:
        return (
            "Discord likely let the interaction token expire. Re-run the command once, and if it repeats, resync commands.",
            "sync",
        )
    if "expected view parameter to be of type view not nonetype" in lowered:
        return (
            "Victor tried to send a follow-up with an empty component payload. Retry after the current deploy, then resync commands once if Discord still looks out of date.",
            "sync",
        )
    if "highrise web api returned 404" in lowered or "highrise web api denied" in lowered:
        return (
            "The Highrise lookup endpoint is rejecting the request. Check the configured API route or try the username again with exact spelling.",
            None,
        )
    if "gateway.discord.gg" in lowered or "clientconnectordnserror" in lowered:
        return (
            "Discord was unreachable for a moment. Give it a beat, then resync commands once if the slash tree still feels stale.",
            "sync",
        )
    if command_name in {"sync"}:
        return (
            "Try resyncing again once. If Discord still disagrees after that, keep the crash thread for the rebuild pass.",
            "sync",
        )
    return (
        "Check the receipts, retry once, and use Apply Fix only when a resync is actually safe for this failure.",
        None,
    )


class CommandAttentionView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Quick Fix",
        style=discord.ButtonStyle.secondary,
        emoji="💿",
        custom_id=f"{COMMAND_ACTION_VIEW_ID}:quick_fix",
    )
    async def quick_fix_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message("Victor misplaced the crash notes.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        quick_fix = _field_value(embed, "Quick Fix") or "No quick fix was attached to this thread. Cute."
        await interaction.response.send_message(quick_fix, ephemeral=True)

    @discord.ui.button(
        label="Apply Fix",
        style=discord.ButtonStyle.danger,
        emoji="📟",
        custom_id=f"{COMMAND_ACTION_VIEW_ID}:apply_fix",
    )
    async def apply_fix_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message("Victor misplaced the crash notes.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        action = (_field_value(embed, "Apply Fix") or "").strip().casefold()
        if not action or action == "none":
            await interaction.response.send_message(
                "No safe auto-fix is attached to this crash thread. Staff eyes only, unfortunately.",
                ephemeral=True,
            )
            return

        admin_cog = interaction.client.get_cog("AdminCog")
        if admin_cog is None:
            await interaction.response.send_message("Victor misplaced his admin desk.", ephemeral=True)
            return
        if action == "sync":
            await admin_cog.handle_console_sync_button(interaction)
            return
        if action == "restart":
            await interaction.response.send_message(
                "Restart is disabled right now. We are in sync-only mode while the command set gets rebuilt.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"Victor does not know how to auto-apply `{action}` yet.",
            ephemeral=True,
        )


class VerifyReviewView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Stamp Pass",
        style=discord.ButtonStyle.success,
        emoji="🕯️",
        custom_id=f"{VERIFY_REVIEW_VIEW_ID}:manual",
    )
    async def manual_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = interaction.client.get_cog("VerifyCog")
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await verify_cog.handle_console_manual_verify_button(interaction)

    @discord.ui.button(
        label="Pull Status",
        style=discord.ButtonStyle.secondary,
        emoji="🖤",
        custom_id=f"{VERIFY_REVIEW_VIEW_ID}:status",
    )
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        verify_cog = interaction.client.get_cog("VerifyCog")
        if verify_cog is None:
            await interaction.response.send_message("Victor misplaced the verification file.", ephemeral=True)
            return
        await verify_cog.handle_console_status_button(interaction)


async def send_command_attention_post(
    bot: commands.Bot,
    cfg: Config,
    *,
    user_id: int,
    command_name: str,
    location: Optional[str],
    details: Optional[str],
    surface: str,
) -> None:
    location_value = "direct messages" if location == "dm" else (f"guild {location}" if location else None)
    command_label = f"/{command_name}" if surface == "slash" else f"!{command_name}"
    embed = build_staff_attention_embed(
        "📟 Command Attention",
        f"`{command_label}` fell apart hard enough that staff should probably look alive.",
        code=_staff_code("Command failure", command_name=command_name),
        tagged_user_id=user_id,
        issue="Command failure",
        location=location_value,
        stage="runtime alert",
        outcome="needs staff eyes",
        details=details,
        next_move="check receipts, decide whether this is a one-off wobble or a real blocker, then use the buttons if the fix is safe.",
        quick_fix=infer_command_fix(command_name, details)[0],
        apply_fix=infer_command_fix(command_name, details)[1],
    )
    await send_log_channel(bot, cfg, embed=embed, view=CommandAttentionView())


async def send_verify_review_post(
    bot: commands.Bot,
    cfg: Config,
    *,
    member: discord.Member,
    highrise_username: str,
    fail_count: int,
    code: str,
    last_error: str,
    max_failures: int,
    bio_preview: str,
) -> None:
    embed = build_staff_attention_embed(
        "🕯️ Verify Review",
        "verification hit the staff desk. the user burned through the automated checks and this case now needs a mod call.",
        color=0xD4A017,
        code=_staff_code("Manual verification review"),
        tagged_user_id=member.id,
        highrise_username=highrise_username,
        issue="Manual verification review",
        location=f"guild {member.guild.id}",
        stage="phase 03 of 03",
        outcome=f"manual review after {fail_count}/{max_failures} misses",
        details=f"verify_code={code} | fail_count={fail_count} | last_error={last_error}",
        bio_preview=bio_preview,
        next_move=(
            "open the member status, compare the current Highrise bio against the issued code, "
            "then manual verify only if the account looks legitimate."
        ),
    )
    await send_log_channel(bot, cfg, embed=embed, view=VerifyReviewView())


async def setup(bot: commands.Bot) -> None:
    bot.add_view(CommandAttentionView())
    bot.add_view(VerifyReviewView())
