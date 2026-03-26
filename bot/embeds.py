import discord
from datetime import datetime, timezone
from typing import List, Optional

COLOR_OK = 0x4A4A4A
COLOR_WARN = 0x8A8A8A
COLOR_ERR = 0x3A3A3A
COLOR_NEUTRAL = 0x2B2B2B

AUTHOR_TAG = "v i c t o r . e x e // away message"
FOOTER_TAG = "c d - r"
TITLE_VERIFY = "🕯️ VICTOR // VERIFY"
TITLE_STATUS = "🖤 VICTOR // STATUS"
TITLE_BLACKMARKET = "💿 VICTOR // BLACKMARKET"
TITLE_REQUEST = "☎️ VICTOR // REQUEST"
TITLE_MATCH = "⛓️ VICTOR // MATCH"
TITLE_HELP = "🦇 VICTOR // HELP"
TITLE_ADMIN = "📟 VICTOR // ADMIN"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def make_embed(title: str, description: str, color: int) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_author(name=AUTHOR_TAG)
    embed.set_footer(text=f"{FOOTER_TAG} // {_timestamp()}")
    return embed


def urgent_embed(code: str, description: str) -> discord.Embed:
    return make_embed(f"🕸️ VICTOR // URGENT // {code}", description, COLOR_ERR)


def _format_verify_issue(label: str) -> str:
    if label == "BIO_TOO_SHORT":
        return "Bio is too short."
    if label == "BIO_TOO_LONG":
        return "Bio is too long."
    if label == "USERNAME":
        return "Highrise username is missing from the bio."
    if label.startswith("FORBIDDEN:"):
        return f"Forbidden pattern matched: `{label.split(':', 1)[1]}`"
    if label.startswith("#"):
        return f"Missing required tag `{label}`"
    return f"Missing required pattern `{label}`"


def _verify_fix_tips(missing_labels: List[str], highrise_username: str) -> str:
    tips: List[str] = []
    if "USERNAME" in missing_labels:
        tips.append(f"Add `{highrise_username}` exactly as written.")
    tag_labels = [label for label in missing_labels if label.startswith("#")]
    if tag_labels:
        tips.append("Add the required tags to the bio.")
    if "BIO_TOO_SHORT" in missing_labels:
        tips.append("Write a fuller bio so it clears the minimum length.")
    if "BIO_TOO_LONG" in missing_labels:
        tips.append("Trim the bio down before resubmitting.")
    forbidden_labels = [label for label in missing_labels if label.startswith("FORBIDDEN:")]
    if forbidden_labels:
        tips.append("Remove blocked wording or patterns.")

    other_patterns = [
        label
        for label in missing_labels
        if label not in {"BIO_TOO_SHORT", "BIO_TOO_LONG", "USERNAME"}
        and not label.startswith("#")
        and not label.startswith("FORBIDDEN:")
    ]
    if other_patterns:
        tips.append("Match the required formatting pattern for this server.")

    if not tips:
        tips.append("Double-check the bio text and try the command again.")

    return "\n".join(f"- {tip}" for tip in tips[:4])


def _verification_stage_summary(verified: str, state: Optional[str], fail_count: Optional[int]) -> str:
    if verified == "YES":
        return "linked cleanly. paperwork closed."
    if verified == "REVIEW":
        return "parked at the staff desk. human judgment required."
    if verified == "PENDING":
        attempts = f" after {fail_count} miss{'es' if fail_count != 1 else ''}" if fail_count else ""
        return f"waiting on the bio update{attempts}."
    return "no live ritual on file."


def verify_success_embed(
    user_mention: str,
    highrise_username: str,
    nickname_changed: bool = False,
    unlocked_roles: Optional[List[str]] = None,
    manual: bool = False,
) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "Verification complete. You survived the ritual. Barely.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="PASS", inline=True)
    notes: List[str] = []
    notes.append("Manual override applied." if manual else "Code matched in the Highrise bio.")
    if nickname_changed:
        notes.append("Nickname updated to the Highrise username.")
    if unlocked_roles:
        notes.append(f"Unlocked roles: {', '.join(unlocked_roles)}")
    embed.add_field(name="[THREAD]", value="approved and closed. no more haunting required.", inline=False)
    embed.add_field(name="[NOTES]", value="\n".join(f"- {note}" for note in notes), inline=False)
    return embed


def verify_code_embed(user_mention: str, highrise_username: str, code: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "new verification thread opened. this is the part where they prove they are not improvising.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[CODE]", value=code, inline=True)
    embed.add_field(
        name="[THREAD]",
        value="phase 01 of 03 // issue code -> update bio -> confirm the recheck",
        inline=False,
    )
    embed.add_field(
        name="[HOW TO CLEAR]",
        value=(
            f"1. put `{code}` somewhere in the Highrise bio\n"
            f"2. keep `{highrise_username}` visible and spelled exactly right\n"
            "3. press the confirm button below so victor can re-scan the profile"
        ),
        inline=False,
    )
    embed.add_field(name="[MOD NOTE]", value="staff only needs to touch this if it rolls into review.", inline=False)
    return embed


def verify_fail_embed(user_mention: str, highrise_username: str, missing_labels: List[str]) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "Verification failed. Tragic. Here is exactly what you need to fix.",
        COLOR_ERR,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="FAIL", inline=True)
    issue_lines = [_format_verify_issue(label) for label in missing_labels] or ["Unknown verification issue."]
    embed.add_field(name="[ISSUES]", value="\n".join(f"- {line}" for line in issue_lines[:8]), inline=False)
    embed.add_field(name="[FIX]", value=_verify_fix_tips(missing_labels, highrise_username), inline=False)
    return embed


def verify_retry_embed(
    user_mention: str,
    highrise_username: str,
    code: str,
    fail_count: int,
    max_failures: int,
) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "the recheck came back ugly. the code still is not in the bio.",
        COLOR_WARN,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[CODE]", value=code, inline=True)
    embed.add_field(name="[FAIL COUNT]", value=f"{fail_count}/{max_failures}", inline=True)
    embed.add_field(
        name="[THREAD]",
        value="phase 02 of 03 // still pending. the user needs to fix the bio before staff should step in.",
        inline=False,
    )
    embed.add_field(
        name="[NEXT]",
        value=(
            "have them update the Highrise bio and press the confirm button again.\n"
            "if the next check misses too, this thread escalates to manual review."
        ),
        inline=False,
    )
    return embed


def verify_manual_review_embed(
    user_mention: str,
    highrise_username: str,
    fail_count: int,
) -> discord.Embed:
    embed = urgent_embed("VERIFY REVIEW", "the ritual stalled out twice. this one belongs to staff now.")
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[FAIL COUNT]", value=str(fail_count), inline=True)
    embed.add_field(
        name="[THREAD]",
        value="phase 03 of 03 // mod review required. check the profile, then either approve it or leave it parked.",
        inline=False,
    )
    embed.add_field(
        name="[NEXT]",
        value="staff can use `!manualverify @user` or `/manualverify` if the member is legitimate.",
        inline=False,
    )
    return embed


def manual_verify_ready_embed(user_mention: str, highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "Manual review approved. I signed the paperwork with visible disdain.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="MANUAL PASS", inline=True)
    embed.add_field(name="[THREAD]", value="staff stamped it through. victor filed the resentment internally.", inline=False)
    return embed


def highrise_user_not_found_embed(highrise_username: str) -> discord.Embed:
    embed = urgent_embed("HIGHRISE", "that username did not resolve in the web api, so this thread dies here.")
    embed.add_field(name="[USERNAME]", value=highrise_username, inline=False)
    embed.add_field(name="[NEXT]", value="check spelling, casing, and whether the account exists publicly.", inline=False)
    return embed


def highrise_api_error_embed(message: str) -> discord.Embed:
    embed = urgent_embed("HIGHRISE API", "the api blinked first. this is a network or endpoint problem, not a user failure.")
    embed.add_field(name="[DETAILS]", value=message[:1024], inline=False)
    embed.add_field(name="[NEXT]", value="retry in a moment. if it keeps happening, staff should check the endpoint path.", inline=False)
    return embed


def status_embed(
    user_mention: str,
    highrise_username: Optional[str],
    verified: str,
    state: Optional[str] = None,
    code: Optional[str] = None,
    fail_count: Optional[int] = None,
) -> discord.Embed:
    embed = make_embed(
        TITLE_STATUS,
        "status board pulled. here is the current state of the ritual.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[VERIFIED]", value=verified, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username or "NONE", inline=True)
    if state:
        embed.add_field(name="[STATE]", value=state, inline=True)
    if code:
        embed.add_field(name="[CODE]", value=code, inline=True)
    if fail_count is not None:
        embed.add_field(name="[FAIL COUNT]", value=str(fail_count), inline=True)
    embed.add_field(
        name="[THREAD]",
        value=_verification_stage_summary(verified, state, fail_count),
        inline=False,
    )
    return embed


def permission_denied_embed(required_role: str) -> discord.Embed:
    embed = urgent_embed("PERMISSION", "Cute. You do not have access.")
    embed.add_field(name="[REQUIRED]", value=required_role, inline=False)
    return embed


def invalid_usage_embed(usage: str) -> discord.Embed:
    embed = urgent_embed("INVALID", "Wrong ritual. Try the documented one.")
    embed.add_field(name="[USAGE]", value=usage, inline=False)
    return embed


def not_found_embed(query: str) -> discord.Embed:
    embed = urgent_embed("NOT FOUND", "I looked. It is not there.")
    embed.add_field(name="[QUERY]", value=query, inline=False)
    return embed


def system_error_embed() -> discord.Embed:
    embed = urgent_embed("SYSTEM", "I blinked. Try again.")
    embed.add_field(name="[ERROR]", value="DB_WRITE_FAIL", inline=False)
    return embed


def blacklisted_embed(reason: Optional[str]) -> discord.Embed:
    embed = urgent_embed("BLACKLIST", "You are not allowed to use this system.")
    if reason:
        embed.add_field(name="[REASON]", value=reason, inline=False)
    return embed


def listing_created_embed(listing_id: int, item_name: str, price: int) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Listing posted. Price it like you mean it.",
        COLOR_OK,
    )
    embed.add_field(name="[ID]", value=str(listing_id), inline=True)
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    embed.add_field(name="[PRICE]", value=str(price), inline=True)
    return embed


def listing_removed_embed(listing_id: int) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Listing pulled. Consider this a mercy.",
        COLOR_WARN,
    )
    embed.add_field(name="[ID]", value=str(listing_id), inline=True)
    return embed


def listings_embed(listings: list) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Open listings. Do not waste my time.",
        COLOR_NEUTRAL,
    )
    if not listings:
        embed.add_field(name="[LISTINGS]", value="NONE", inline=False)
        return embed
    lines = ["ID | ITEM | PRICE"]
    for row in listings:
        lines.append(f"{row['id']} | {row['item_name']} | {row['price']}")
    embed.add_field(name="[LISTINGS]", value="```\n" + "\n".join(lines) + "\n```", inline=False)
    return embed


def request_created_embed(request_id: int, item_name: str, max_price: int) -> discord.Embed:
    embed = make_embed(
        TITLE_REQUEST,
        "Request logged. Try not to embarrass yourself.",
        COLOR_OK,
    )
    embed.add_field(name="[ID]", value=str(request_id), inline=True)
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    embed.add_field(name="[MAX]", value=str(max_price), inline=True)
    return embed


def request_cancelled_embed(request_id: int) -> discord.Embed:
    embed = make_embed(
        TITLE_REQUEST,
        "Request cancelled. I closed the file.",
        COLOR_WARN,
    )
    embed.add_field(name="[ID]", value=str(request_id), inline=True)
    return embed


def no_sellers_embed(item_name: str) -> discord.Embed:
    embed = make_embed(
        TITLE_MATCH,
        "No sellers. You are alone right now.",
        COLOR_WARN,
    )
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    return embed


def match_alert_embed(match_id: int, item_name: str, max_price: int) -> discord.Embed:
    embed = make_embed(
        TITLE_MATCH,
        "You have a buyer. Try to look alive.",
        COLOR_WARN,
    )
    embed.add_field(name="[MATCH]", value=str(match_id), inline=True)
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    embed.add_field(name="[MAX]", value=str(max_price), inline=True)
    embed.add_field(name="[ACTION]", value="!accept or !decline", inline=False)
    return embed


def match_accepted_embed(match_id: int) -> discord.Embed:
    embed = make_embed(
        TITLE_MATCH,
        "Accepted. Do not embarrass me.",
        COLOR_OK,
    )
    embed.add_field(name="[MATCH]", value=str(match_id), inline=True)
    return embed


def match_declined_embed(match_id: int) -> discord.Embed:
    embed = make_embed(
        TITLE_MATCH,
        "Declined. That was inevitable.",
        COLOR_WARN,
    )
    embed.add_field(name="[MATCH]", value=str(match_id), inline=True)
    return embed


def help_embed() -> discord.Embed:
    embed = make_embed(
        TITLE_HELP,
        "Pick a path from the menu. Do not get sentimental.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[VERIFY]", value="!verify, !status", inline=True)
    embed.add_field(name="[MARKET]", value="!blackmarket, !help blackmarket", inline=True)
    embed.add_field(name="[MATCH]", value="!request, !accept, !decline", inline=True)
    embed.add_field(name="[ADMIN]", value="!blacklist, !sync, !restart, !manualverify", inline=False)
    embed.add_field(
        name="[VERIFY FLOW]",
        value="`!verify @user username` checks Highrise and issues a code. After the user updates their Highrise bio, they press the confirmation button on Victor's message so he can re-check it. `!manualverify` is the staff fallback.",
        inline=False,
    )
    embed.add_field(
        name="[DEEP HELP]",
        value="!help verify | !help sync | !help request | /help verify",
        inline=False,
    )
    embed.add_field(name="[MENU]", value="Use the select menu or the quick buttons below.", inline=False)
    return embed


def blacklist_added_embed(user_mention: str) -> discord.Embed:
    embed = make_embed(
        TITLE_ADMIN,
        "Blacklist updated. Do not test me.",
        COLOR_WARN,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[STATUS]", value="BLACKLISTED", inline=True)
    return embed


def blacklist_removed_embed(user_mention: str) -> discord.Embed:
    embed = make_embed(
        TITLE_ADMIN,
        "Blacklist removed. Do not get comfortable.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[STATUS]", value="CLEARED", inline=True)
    return embed


def blacklist_list_embed(entries: list) -> discord.Embed:
    embed = make_embed(
        TITLE_ADMIN,
        "Current blacklist.",
        COLOR_NEUTRAL,
    )
    if not entries:
        embed.add_field(name="[LIST]", value="EMPTY", inline=False)
        return embed
    lines = ["ID | USER | REASON"]
    for row in entries:
        reason = row.get("reason") or "NONE"
        lines.append(f"{row['id']} | {row['discord_id']} | {reason}")
    embed.add_field(name="[LIST]", value="```\n" + "\n".join(lines) + "\n```", inline=False)
    return embed


def match_closed_embed(match_id: int) -> discord.Embed:
    embed = urgent_embed("MATCH CLOSED", "Too late. I closed it.")
    embed.add_field(name="[MATCH]", value=str(match_id), inline=True)
    return embed
