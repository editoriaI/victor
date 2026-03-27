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
    if state == "STAFF REVIEW":
        return "waiting at the staff desk for a yes or no."
    if state == "RETRY REQUESTED":
        attempts = f" after {fail_count} rejection{'s' if fail_count != 1 else ''}" if fail_count else ""
        return f"staff kicked it back for another pass{attempts}."
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
    captured: bool = False,
) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ VERIFICATION COMPLETE \u2714 ]\n\nSigned. Filed. Buried in the system.\n\nYour username is now on record.\nDo not make me reopen this file.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="PASS", inline=True)
    notes: List[str] = []
    if manual:
        notes.append("Manual override applied.")
    elif captured:
        notes.append("Highrise username captured from member intake.")
    else:
        notes.append("Code matched in the Highrise bio.")
    if nickname_changed:
        notes.append("Nickname updated to the Highrise username.")
    if unlocked_roles:
        notes.append(f"Unlocked roles: {', '.join(unlocked_roles)}")
    embed.add_field(name="[THREAD]", value="thread closed. system remains stable. barely.", inline=False)
    embed.add_field(name="[NOTES]", value="\n".join(f"- {note}" for note in notes), inline=False)
    return embed


def verify_submission_received_embed(user_mention: str, highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ INTAKE RECEIVED ]\n\nGood. It's on the desk now.\n\nStaff will decide if this belongs in the system\nor back in your drafts where it came from.\n\nTry patience. It builds character.",
        COLOR_WARN,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[STATE]", value="AWAITING STAFF REVIEW", inline=True)
    embed.add_field(
        name="[THREAD]",
        value="staff will confirm the username from the console post. once they approve it, victor closes the loop.",
        inline=False,
    )
    return embed


def verify_rejected_embed(user_mention: str, highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ VERIFICATION REJECTED \u2716 ]\n\nStaff sent that back.\n\nEither it's wrong, messy, or you got creative\nwhen no one asked you to.\n\nSubmit it again. Correctly this time.",
        COLOR_ERR,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="REJECTED", inline=True)
    embed.add_field(
        name="[NEXT]",
        value="run `verify` again and resubmit the correct username. victor is capable of patience in very small doses.",
        inline=False,
    )
    return embed


def verify_staff_approved_embed(user_mention: str, highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ INTAKE APPROVED \u2714 ]\n\nUsername cleared.\n\nFiled. Updated. Thread closed.\nSystem integrity preserved.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="APPROVED", inline=True)
    return embed


def verify_staff_rejected_embed(user_mention: str, highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ INTAKE REJECTED \u2716 ]\n\nUsername denied.\n\nReturned to user for a cleaner submission.\nTry again when it looks like you meant it.",
        COLOR_ERR,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="REJECTED", inline=True)
    return embed


def verify_staff_action_result_embed(action: str, user_mention: str, channel_mention: Optional[str] = None) -> discord.Embed:
    action = action.casefold()
    if action == "approved":
        description = "[ STAFF NOTE ]\n\nApproved.\n\nThe user-facing receipt has been posted where they can actually see it."
        color = COLOR_OK
    else:
        description = "[ STAFF NOTE ]\n\nRejected.\n\nThe user-facing receipt has been posted and the file is waiting on a cleaner resubmission."
        color = COLOR_WARN

    embed = make_embed(TITLE_ADMIN, description, color)
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    if channel_mention:
        embed.add_field(name="[POSTED IN]", value=channel_mention, inline=True)
    return embed


def verify_prompt_embed(user_mention: str, existing_username: Optional[str] = None) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ INTAKE THREAD OPENED ]\n\nStay still.\n\nVictor only needs your Highrise username.\nKeep it clean. Keep it exact.\n\nThis record is permanent. I would prefer not to fix it later.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[REQUEST]", value="Highrise username", inline=True)
    embed.add_field(name="[MODE]", value="member intake", inline=True)
    embed.add_field(
        name="[THREAD]",
        value="click the button below, drop your HR username into the prompt, and victor will hand it to staff for a clean sign-off.",
        inline=False,
    )
    if existing_username:
        embed.add_field(name="[ON FILE]", value=existing_username, inline=True)
    embed.add_field(
        name="[WHY]",
        value="this keeps Discord-side verification readable without asking people to trade or prove anything off-platform.",
        inline=False,
    )
    return embed


def verify_channel_redirect_embed(channel_mention: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ VERIFY LIVES HERE ]\n\nVictor only handles Highrise intake inside the designated lane.\n\nHead to "
        f"{channel_mention} and run it there so the whole paper trail stays in one place.",
        COLOR_WARN,
    )
    embed.add_field(
        name="[NEXT]",
        value=f"open {channel_mention}, run `verify`, and follow the intake prompt.",
        inline=False,
    )
    return embed


def verify_private_intake_embed(channel_mention: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ PRIVATE INTAKE ONLY ]\n\nVictor keeps the actual intake prompt private.\n\nUse `/verify` in the verify lane so your username submission stays off the public floor.",
        COLOR_WARN,
    )
    embed.add_field(
        name="[WHERE]",
        value=channel_mention,
        inline=True,
    )
    embed.add_field(
        name="[NEXT]",
        value=f"go to {channel_mention} and run `/verify` for the private intake prompt.",
        inline=False,
    )
    return embed


def verify_join_embed(user_mention: str, verify_channel_mention: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ VERIFY ON JOIN ]\n\nWelcome in.\n\nBefore you get too comfortable, get your Highrise username on file.\nVictor would prefer not to guess who you are later.",
        COLOR_WARN,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[START HERE]", value=verify_channel_mention, inline=True)
    embed.add_field(name="[WHY]", value="keep your Highrise username logged cleanly from day one.", inline=True)
    embed.add_field(
        name="[HOW TO VERIFY]",
        value=(
            f"1. Go to {verify_channel_mention}\n"
            "2. Run `/verify` or `!verify`\n"
            "3. Submit your exact Highrise username\n"
            "4. Wait for staff approval"
        ),
        inline=False,
    )
    embed.add_field(
        name="[WHAT HAPPENS NEXT]",
        value=(
            "once staff clears it, Victor logs the username, updates your nickname when possible, "
            "and keeps your record readable."
        ),
        inline=False,
    )
    embed.add_field(
        name="[IMPORTANT]",
        value=(
            "use the exact Highrise handle you want on file. if staff rejects it, just run verify again and resend it cleanly."
        ),
        inline=False,
    )
    return embed


def verify_current_members_embed(verify_channel_mention: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ CURRENT MEMBERS CHECK-IN ]\n\nIf your Highrise username is not on file yet, now would be an excellent time to fix that.\n\nVictor is cleaning up the books.",
        COLOR_NEUTRAL,
    )
    embed.add_field(
        name="[WHERE TO GO]",
        value=f"use {verify_channel_mention} for `/verify`, `!verify`, `/status`, or `!status`.",
        inline=False,
    )
    embed.add_field(
        name="[HOW IT WORKS]",
        value="submit your exact Highrise username, wait for staff approval, and let Victor close the file properly.",
        inline=False,
    )
    return embed


def victor_intro_embed(user_mention: str, verify_channel_mention: Optional[str] = None) -> discord.Embed:
    embed = make_embed(
        TITLE_HELP,
        "[ SYSTEM ONLINE ]\n\n...\n\n...\n\nConnection established.\n\n"
        "I\u2019m Victor.\n\n"
        "Intake handler. Record keeper. Reluctant backbone of this server\u2019s structure.\n\n"
        "I was brought online to correct a recurring issue:\n"
        "none of you were organized.\n\n"
        "So now I collect Highrise usernames.\n"
        "I pass them to staff for approval.\n"
        "I log what survives.\n"
        "I return what doesn\u2019t.\n\n"
        "No more bio rituals.\n"
        "Just clean intake and permanent records.\n\n"
        "And to be clear\u2014\n\n"
        "If you intend to use this server properly,\n"
        "you will need to be verified.\n\n"
        "Unlogged users don\u2019t get full access.\n"
        "That\u2019s not personal. That\u2019s structure.\n\n"
        "Run `/verify` and enter the system.\n\n"
        "Or don\u2019t.\n\n"
        "Just understand some doors will remain closed,\n"
        "and I won\u2019t be the one opening them for you.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[TAGGED]", value=user_mention, inline=True)
    embed.add_field(name="[ROLE]", value="Highrise intake + staff-signoff desk", inline=True)
    embed.add_field(name="[MOOD]", value="professionally unbothered. suspiciously dedicated.", inline=True)
    embed.add_field(
        name="[WHAT I HANDLE]",
        value=(
            "- Highrise username intake\n"
            "- staff approval and rejection flow\n"
            "- status checks on who's logged and who's still stalling"
        ),
        inline=False,
    )
    if verify_channel_mention:
        embed.add_field(
            name="[START HERE]",
            value=(
                f"go to {verify_channel_mention} and run `/verify`.\n"
                "that is the lane. use it."
            ),
            inline=False,
        )
    embed.add_field(
        name="[CURRENT STATE]",
        value="verify is live, routed to the proper lane, and staff now signs off before anything gets buried in the system. cleaner records. fewer excuses.",
        inline=False,
    )
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
        "[ MANUAL OVERRIDE ACCEPTED ]\n\nStaff stepped in.\n\nYour username has been forced through the system\nwith visible reluctance on my end.\n\nYou're set. Don't make it weird.",
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


def verify_missing_record_embed(user_mention: str) -> discord.Embed:
    embed = make_embed(
        TITLE_STATUS,
        "[ STATUS: EMPTY ]\n\nThere is no intake on file for you.\n\nWhich means you've done nothing.\nFix that.",
        COLOR_WARN,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[NEXT]", value="run `!verify`, `/verify`, or use the Verify button from `menu` to open intake.", inline=False)
    return embed


def status_embed(
    user_mention: str,
    highrise_username: Optional[str],
    verified: str,
    state: Optional[str] = None,
    code: Optional[str] = None,
    fail_count: Optional[int] = None,
) -> discord.Embed:
    descriptions = {
        "STAFF REVIEW": "[ STATUS: PENDING ]\n\nYour intake is sitting on the staff desk.\n\nWaiting. Judged. Unmoved.\n\nYou'll know when they care.",
        "RETRY REQUESTED": "[ STATUS: RETURNED ]\n\nStaff bounced your username back.\n\nClean it up. Resubmit it.\nWe will attempt this again without the chaos.",
        "USERNAME LOGGED": "[ STATUS: LOGGED \u2714 ]\n\nUsername is on file.\n\nThread closed. Paperwork survived.\nSystem remains stable. Barely.",
        "NO DATA": "[ STATUS: EMPTY ]\n\nThere is no intake on file for you.\n\nWhich means you've done nothing.\nFix that.",
    }
    embed = make_embed(
        TITLE_STATUS,
        descriptions.get(state or "", "[ STATUS ]\n\nVictor found a file. It's readable enough."),
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
    if state == "RETRY REQUESTED":
        embed.add_field(name="[NEXT]", value="submit `verify` again with the corrected Highrise username.", inline=False)
    return embed


def permission_denied_embed(required_role: str) -> discord.Embed:
    embed = urgent_embed("PERMISSION", "[ ACCESS DENIED ]\n\nThat lane is not yours.\n\nAnd no, asking again will not change that.")
    embed.add_field(name="[REQUIRED]", value=required_role, inline=False)
    return embed


def invalid_usage_embed(usage: str) -> discord.Embed:
    embed = urgent_embed("INVALID", "[ INVALID INPUT ]\n\nThat was not the command.\n\nFollow the structure like everyone else\nor continue guessing. I'll be here either way.")
    embed.add_field(name="[USAGE]", value=usage, inline=False)
    return embed


def not_found_embed(query: str) -> discord.Embed:
    embed = urgent_embed("NOT FOUND", "I looked. It is not there.")
    embed.add_field(name="[QUERY]", value=query, inline=False)
    return embed


def system_error_embed() -> discord.Embed:
    embed = urgent_embed("SYSTEM", "[ SYSTEM INTERRUPTION ]\n\nSomething broke.\n\nEven I noticed.\n\nTry again.")
    embed.add_field(name="[ERROR]", value="DB_WRITE_FAIL", inline=False)
    return embed


def blacklisted_embed(reason: Optional[str]) -> discord.Embed:
    embed = urgent_embed("BLACKLIST", "[ ACCESS REVOKED ]\n\nYou are not permitted to use this system.\n\nThis is intentional.")
    if reason:
        embed.add_field(name="[REASON]", value=reason, inline=False)
    return embed


def sync_success_embed(synced_count: int) -> discord.Embed:
    embed = make_embed(
        TITLE_ADMIN,
        "[ SYNC COMPLETE \u2714 ]\n\nSlash tree resynced.\n\nSystem aligned. I can breathe again.\nFiguratively.",
        COLOR_OK,
    )
    embed.add_field(name="[SYNCED]", value=str(synced_count), inline=True)
    return embed


def approval_dm_embed(highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "Your Highrise username has been approved and logged.\n\nYou're clear.\n\nTry not to come back through this system again.",
        COLOR_OK,
    )
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    return embed


def rejection_dm_embed(highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "Your username was not approved.\n\nRun verify again and submit the exact Highrise handle\nyou want permanently on file.\n\nPrecision matters more than confidence here.",
        COLOR_ERR,
    )
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
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
        "pick a live thread from the menu. the rest are still backstage.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[MENU]", value="!menu, /menu", inline=True)
    embed.add_field(name="[VERIFY]", value="!verify, !manualverify, !status", inline=True)
    embed.add_field(name="[ADMIN]", value="!sync, /sync", inline=True)
    embed.add_field(name="[PARKED]", value="blackmarket, matchmaking, restart", inline=True)
    embed.add_field(
        name="[VERIFY FLOW]",
        value="`verify` opens intake, collects the member's Highrise username, and stores it on file. `manualverify` stays available for staff corrections or overrides.",
        inline=False,
    )
    embed.add_field(
        name="[DEEP HELP]",
        value="!menu | !help verify | !help status | !help sync | !help parked",
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
