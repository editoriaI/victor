import json
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
TITLE_BANK = "🏦 VICTOR // BANK"


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
    recognition_note: Optional[str] = None,
    trusted_roles: Optional[List[str]] = None,
    primary_role: Optional[str] = None,
) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ VERIFICATION COMPLETE \u2714 ]\n\nYour Highrise username is locked in and the tidy file is sealed.\nYou’re cleared to move on—staff already gave the green light.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[RESULT]", value="PASS", inline=True)
    if primary_role:
        embed.add_field(name="[ROLE]", value=primary_role, inline=True)
    notes: List[str] = []
    if trusted_roles:
        embed.add_field(name="[TRUSTED]", value=", ".join(trusted_roles), inline=True)
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
    if recognition_note:
        notes.append(recognition_note)
    embed.add_field(name="[THREAD]", value="thread closed. system remains stable. barely.", inline=False)
    embed.add_field(name="[NOTES]", value="\n".join(f"- {note}" for note in notes), inline=False)
    return embed


def verify_submission_received_embed(user_mention: str, highrise_username: str) -> discord.Embed:
    embed = make_embed(
        TITLE_VERIFY,
        "[ INTAKE RECEIVED ]\n\nNice work! Staff has your username and is reviewing it now.\nYou’ll get a quick update once they approve or suggest tweaks, so stay calm and know the file is moving.",
        COLOR_WARN,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[STATE]", value="AWAITING STAFF REVIEW", inline=True)
    embed.add_field(
        name="[THREAD]",
        value="Staff will confirm the username from the console post, and Victor closes the loop once it’s done.",
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
        "[ INTAKE THREAD OPENED ]\n\nThanks for keeping us organized! Drop your exact Highrise username and Victor will relay it to staff.\nThe cleaner the entry, the faster the desk can seal it up, and this thread closes itself once the intake finishes.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[REQUEST]", value="Highrise username", inline=True)
    embed.add_field(name="[MODE]", value="member intake", inline=True)
    embed.add_field(
        name="[THREAD]",
        value="Hit the button, paste your username, and Victor will keep the record tidy while staff signs off.",
        inline=False,
    )
    if existing_username:
        embed.add_field(name="[ON FILE]", value=existing_username, inline=True)
    embed.add_field(
        name="[WHY]",
        value="We keep everything readable without asking for private proof—just your clean Highrise handle.",
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
        "[ VERIFY INTAKE ]\n\nVictor runs intake in the verify lane.\n\nUse `!verify` there and the prompt will open without making a mess on the public floor.",
        COLOR_WARN,
    )
    embed.add_field(
        name="[WHERE]",
        value=channel_mention,
        inline=True,
    )
    embed.add_field(
        name="[NEXT]",
        value=f"go to {channel_mention} and run `!verify` to open intake.",
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
            "2. Run `!verify`\n"
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
        value=f"use {verify_channel_mention} for `!verify` and `!status`.",
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
        "Run `!verify` and enter the system.\n\n"
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
                f"go to {verify_channel_mention} and run `!verify`.\n"
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
        "The recheck needs a redo: the code isn't in the bio yet, but you're almost there.",
        COLOR_WARN,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username, inline=True)
    embed.add_field(name="[CODE]", value=code, inline=True)
    embed.add_field(name="[FAIL COUNT]", value=f"{fail_count}/{max_failures}", inline=True)
    embed.add_field(
        name="[THREAD]",
        value="phase 02 of 03 • waiting on the bio update. quick fix? edit the bio and hit confirm again.",
        inline=False,
    )
    embed.add_field(
        name="[NEXT]",
        value="ask the member to update their Highrise bio, rerun the check, and let this thread timeout itself before staff leaps in.",
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
    embed.add_field(name="[NEXT]", value="run `!verify` or use the Verify button from `!menu` to open intake.", inline=False)
    return embed


def status_embed(
    user_mention: str,
    highrise_username: Optional[str],
    verified: str,
    state: Optional[str] = None,
    code: Optional[str] = None,
    fail_count: Optional[int] = None,
    trusted_roles: Optional[List[str]] = None,
    primary_role: Optional[str] = None,
    db_status: Optional[str] = None,
    guidance: Optional[str] = None,
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
    if primary_role:
        embed.add_field(name="[ROLE]", value=primary_role, inline=True)
    if state:
        embed.add_field(name="[STATE]", value=state, inline=True)
    if code:
        embed.add_field(name="[CODE]", value=code, inline=True)
    if fail_count is not None:
        embed.add_field(name="[FAIL COUNT]", value=str(fail_count), inline=True)
    if trusted_roles:
        embed.add_field(name="[TRUSTED]", value=", ".join(trusted_roles), inline=True)
    if db_status:
        embed.add_field(name="[DB STATUS]", value=db_status, inline=True)
    embed.add_field(
        name="[THREAD]",
        value=_verification_stage_summary(verified, state, fail_count),
        inline=False,
    )
    if state == "RETRY REQUESTED":
        embed.add_field(name="[NEXT]", value="submit `verify` again with the corrected Highrise username.", inline=False)
    if guidance:
        embed.add_field(name="[GUIDANCE]", value=guidance, inline=False)
    return embed


def victor_patch_note_embed(user_mention: str, verify_channel_mention: Optional[str] = None) -> discord.Embed:
    embed = make_embed(
        TITLE_HELP,
        "[ PATCH NOTE // VICTOR LIVE UPDATE ]\n\nSignal received.\nVictor has moved out of the old speech loop and into cleaner live ops.\n\nVerification stays structured.\nMarket lanes are getting sharper.\nTrusted traffic now has its own gravity.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[TAGGED]", value=user_mention, inline=True)
    embed.add_field(name="[BUILD]", value="market routing + gold desk", inline=True)
    embed.add_field(name="[STATUS]", value="live and being refined in public", inline=True)
    embed.add_field(
        name="[LIVE LANES]",
        value=(
            "- verify intake and status desk\n"
            "- market board for buying and selling\n"
            "- gold routing for looking / selling / trusted overflow"
        ),
        inline=False,
    )
    if verify_channel_mention:
        embed.add_field(
            name="[VERIFY START]",
            value=f"verification still begins in {verify_channel_mention} with `!verify`.",
            inline=False,
        )
    embed.add_field(
        name="[PATCH MOOD]",
        value="Less monologue. More movement. Cleaner paper trail. Same attitude.",
        inline=False,
    )
    return embed


def permission_denied_embed(required_role: str) -> discord.Embed:
    embed = urgent_embed("PERMISSION", "[ ACCESS DENIED ]\n\nThat lane is not yours.\n\nAnd no, asking again will not change that.")
    embed.add_field(name="[REQUIRED]", value=required_role, inline=False)
    return embed


def invalid_usage_embed(usage: str) -> discord.Embed:
    embed = urgent_embed("INVALID", "[ INVALID INPUT ]\n\nThat was not the command.\n\nFollow the structure like everyone else\nor continue guessing. I'll be here either way.")
    embed.add_field(name="[USAGE]", value=usage, inline=False)
    return embed


def bank_profile_required_embed() -> discord.Embed:
    embed = make_embed(
        TITLE_BANK,
        "[ BANK PROFILE MISSING ]\n\nVictor cannot open the account view yet because this member does not have a linked Highrise identity on file.",
        COLOR_WARN,
    )
    embed.add_field(
        name="[NEXT]",
        value="Finish verification first so Victor can tie the banking record to the correct member.",
        inline=False,
    )
    return embed


def bank_balance_embed(
    *,
    user_mention: str,
    highrise_username: str,
    checking_balance: int,
    savings_balance: int,
    total_balance: int,
    recent_count: int,
) -> discord.Embed:
    embed = make_embed(
        TITLE_BANK,
        "[ ACCOUNT SUMMARY ]\n\nVictor pulled the current ledger view for this member.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[HIGHRISE]", value=highrise_username or "UNLINKED", inline=True)
    embed.add_field(name="[TOTAL]", value=f"{total_balance:,} gold", inline=True)
    embed.add_field(name="[CHECKING]", value=f"{checking_balance:,} gold", inline=True)
    embed.add_field(name="[SAVINGS]", value=f"{savings_balance:,} gold", inline=True)
    embed.add_field(name="[RECENT]", value=f"{recent_count} transaction(s)", inline=True)
    embed.add_field(
        name="[NOTE]",
        value="Checking is the live transfer lane. Savings is tracked separately for later withdrawal work.",
        inline=False,
    )
    return embed


def bank_transactions_embed(
    *,
    user_mention: str,
    transactions: List[dict],
) -> discord.Embed:
    embed = make_embed(
        TITLE_BANK,
        "[ RECENT ACTIVITY ]\n\nVictor pulled the latest transaction receipts tied to this member.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=False)
    if not transactions:
        embed.add_field(name="[LEDGER]", value="No transactions on file yet.", inline=False)
        return embed

    lines = []
    for transaction in transactions[:5]:
        metadata_raw = transaction.get("metadata") or "{}"
        try:
            metadata = json.loads(metadata_raw)
        except Exception:
            metadata = {}
        note = metadata.get("note") or transaction.get("reference_type") or "bank event"
        lines.append(
            f"`#{transaction['id']}` {transaction['transaction_type']} • {int(transaction['amount']):,} gold • {note}"
        )
    embed.add_field(name="[LEDGER]", value="\n".join(lines), inline=False)
    return embed


def bank_transfer_success_embed(
    *,
    sender_mention: str,
    recipient_mention: str,
    amount: int,
    sender_balance_after: int,
    note: str,
) -> discord.Embed:
    embed = make_embed(
        TITLE_BANK,
        "[ TRANSFER POSTED ]\n\nVictor moved the funds across the internal ledger and stamped the receipt.",
        COLOR_OK,
    )
    embed.add_field(name="[FROM]", value=sender_mention, inline=True)
    embed.add_field(name="[TO]", value=recipient_mention, inline=True)
    embed.add_field(name="[AMOUNT]", value=f"{amount:,} gold", inline=True)
    embed.add_field(name="[CHECKING LEFT]", value=f"{sender_balance_after:,} gold", inline=True)
    embed.add_field(name="[NOTE]", value=note or "No note attached.", inline=False)
    return embed


def bank_transfer_error_embed(message: str) -> discord.Embed:
    embed = make_embed(
        TITLE_BANK,
        "[ TRANSFER BLOCKED ]\n\nVictor refused to move the funds.",
        COLOR_WARN,
    )
    embed.add_field(name="[WHY]", value=message, inline=False)
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
        "[ SYNC COMPLETE \u2714 ]\n\nCommand registry refreshed.\n\nSystem aligned. I can breathe again.\nFiguratively.",
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


def market_trade_post_embed(
    *,
    asset_type: str,
    action: str,
    user_mention: str,
    item_name: str,
    price: int,
    details: str,
    trusted_roles: Optional[List[str]] = None,
    duplicate_count: int = 1,
) -> discord.Embed:
    normalized_action = action.casefold()
    normalized_asset = (asset_type or "market").strip().casefold()
    title = "SELL" if normalized_action == "sell" else "BUY"
    verb = "selling" if normalized_action == "sell" else "buying"
    asset_label = normalized_asset.upper()
    embed = make_embed(
        f"{TITLE_BLACKMARKET} // {asset_label} {title}",
        f"{asset_label.title()} lane is live. {user_mention} is {verb} and Victor posted the call clean.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    embed.add_field(name="[PRICE]", value=str(price), inline=True)
    embed.add_field(name="[DETAILS]", value=details[:1024], inline=False)
    if trusted_roles:
        embed.add_field(name="[TRUSTED]", value=", ".join(trusted_roles), inline=True)
    embed.add_field(name="[POSTS]", value=str(max(1, duplicate_count)), inline=True)
    embed.add_field(name="[LANE]", value=f"{normalized_asset} > {normalized_action} > gather info > post", inline=True)
    return embed


def market_trade_posted_embed(
    *,
    asset_type: str,
    action: str,
    item_name: str,
    price: int,
    duplicate_count: int,
    trusted_roles: Optional[List[str]] = None,
) -> discord.Embed:
    normalized_asset = (asset_type or "market").strip().casefold()
    boost_note = "trusted boost applied." if duplicate_count > 1 else "single post sent."
    embed = make_embed(
        TITLE_BLACKMARKET,
        f"{normalized_asset.title()} {action.casefold()} post is out. {boost_note}",
        COLOR_OK,
    )
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    embed.add_field(name="[PRICE]", value=str(price), inline=True)
    embed.add_field(name="[POSTS]", value=str(duplicate_count), inline=True)
    if trusted_roles:
        embed.add_field(name="[TRUSTED]", value=", ".join(trusted_roles), inline=False)
    return embed


def market_cooldown_embed(minutes_left: int, lane_label: str) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Cooldown active. Let the current post breathe before you throw another one at the wall.",
        COLOR_WARN,
    )
    embed.add_field(name="[LANE]", value=lane_label, inline=True)
    embed.add_field(name="[WAIT]", value=f"{max(1, minutes_left)} minute(s)", inline=True)
    return embed


def market_match_beta_embed(match_count: int, *, asset_type: str) -> discord.Embed:
    normalized_asset = (asset_type or "market").strip().casefold()
    embed = make_embed(
        TITLE_MATCH,
        f"Beta match scan ran against the live {normalized_asset} board.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[MATCHES]", value=str(match_count), inline=True)
    embed.add_field(name="[MODE]", value="beta", inline=True)
    embed.add_field(
        name="[NOTE]",
        value="This is a soft signal for now. Victor is only checking the board and reporting possible overlap.",
        inline=False,
    )
    return embed


def gold_trade_post_embed(
    *,
    action: str,
    user_mention: str,
    item_name: str,
    price: int,
    details: str,
    trusted_roles: Optional[List[str]] = None,
    duplicate_count: int = 1,
) -> discord.Embed:
    return market_trade_post_embed(
        asset_type="gold",
        action=action,
        user_mention=user_mention,
        item_name=item_name,
        price=price,
        details=details,
        trusted_roles=trusted_roles,
        duplicate_count=duplicate_count,
    )


def gold_trade_posted_embed(
    *,
    action: str,
    item_name: str,
    price: int,
    duplicate_count: int,
    trusted_roles: Optional[List[str]] = None,
) -> discord.Embed:
    return market_trade_posted_embed(
        asset_type="gold",
        action=action,
        item_name=item_name,
        price=price,
        duplicate_count=duplicate_count,
        trusted_roles=trusted_roles,
    )


def gold_match_beta_embed(match_count: int) -> discord.Embed:
    return market_match_beta_embed(match_count, asset_type="gold")


def price_check_post_embed(*, user_mention: str, item_name: str, details: str) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Price check filed. The board can weigh in without the whole lane turning into static.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    embed.add_field(name="[LANE]", value="price checks", inline=True)
    embed.add_field(name="[DETAILS]", value=details[:1024], inline=False)
    return embed


def price_check_posted_embed(item_name: str, channel_mention: Optional[str]) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Price check sent.",
        COLOR_OK,
    )
    embed.add_field(name="[ITEM]", value=item_name, inline=True)
    embed.add_field(name="[CHANNEL]", value=channel_mention or "current channel", inline=True)
    return embed


def proof_of_sale_post_embed(*, user_mention: str, details: str) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Vouch logged. Proof stays in one lane instead of getting lost in side chatter.",
        COLOR_OK,
    )
    embed.add_field(name="[USER]", value=user_mention, inline=True)
    embed.add_field(name="[LANE]", value="proof of selling", inline=True)
    embed.add_field(name="[DETAILS]", value=details[:1024], inline=False)
    return embed


def proof_of_sale_posted_embed(channel_mention: Optional[str]) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Vouch post sent.",
        COLOR_OK,
    )
    embed.add_field(name="[CHANNEL]", value=channel_mention or "current channel", inline=False)
    return embed


def vouch_import_summary_embed(
    *,
    channel_mention: Optional[str],
    scanned: int,
    inserted: int,
    updated: int,
    skipped: int,
) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Vouch skim complete. Victor indexed what he could find.",
        COLOR_OK,
    )
    embed.add_field(name="[CHANNEL]", value=channel_mention or "proof lane", inline=True)
    embed.add_field(name="[SCANNED]", value=str(scanned), inline=True)
    embed.add_field(name="[INSERTED]", value=str(inserted), inline=True)
    embed.add_field(name="[UPDATED]", value=str(updated), inline=True)
    embed.add_field(name="[SKIPPED]", value=str(skipped), inline=True)
    return embed


def vouch_lookup_embed(
    *,
    member_mention: str,
    total_count: int,
    rows: list[dict],
) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Vouch file pulled from Victor's proof index.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[MEMBER]", value=member_mention, inline=True)
    embed.add_field(name="[TOTAL]", value=str(total_count), inline=True)
    if not rows:
        embed.add_field(name="[VOUCHES]", value="None on file yet.", inline=False)
        return embed

    lines: list[str] = []
    for row in rows[:4]:
        preview = " ".join((row.get("details") or "").split())
        if len(preview) > 60:
            preview = preview[:57].rstrip() + "..."
        voucher = f"<@{row['voucher_discord_id']}>" if row.get("voucher_discord_id") else "unknown"
        jump = row.get("source_url") or ""
        line = f"{voucher} - {preview}"
        if jump:
            line += f" [jump]({jump})"
        lines.append(line)
    embed.add_field(name="[RECENT]", value="\n".join(lines), inline=False)
    return embed


def listing_removed_embed(listing_id: int) -> discord.Embed:
    embed = make_embed(
        TITLE_BLACKMARKET,
        "Listing pulled. Consider this a mercy.",
        COLOR_WARN,
    )
    embed.add_field(name="[ID]", value=str(listing_id), inline=True)
    return embed


def market_trade_removed_embed(
    *,
    asset_type: str,
    action: str,
    post_count: int,
    deleted_count: int,
) -> discord.Embed:
    normalized_asset = (asset_type or "market").strip().casefold()
    normalized_action = (action or "sell").strip().casefold()
    embed = make_embed(
        TITLE_BLACKMARKET,
        f"{normalized_asset.title()} {normalized_action} post pulled.",
        COLOR_WARN,
    )
    embed.add_field(name="[POSTS CLOSED]", value=str(max(1, post_count)), inline=True)
    embed.add_field(name="[MESSAGES REMOVED]", value=str(max(0, deleted_count)), inline=True)
    embed.add_field(name="[LANE]", value=f"{normalized_asset} > {normalized_action}", inline=True)
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
        "Open the menu and pick the lane you need. Victor handles verification, market activity, and a few staff tools from one place.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[OPEN MENU]", value="!menu", inline=True)
    embed.add_field(name="[VERIFY]", value="!verify, !updateusername, !status", inline=True)
    embed.add_field(name="[MARKET]", value="!blackmarket, !request, !accept, !decline", inline=True)
    embed.add_field(
        name="[MEMBER HELP]",
        value="Use Verify to get your Highrise username on file, Status to check progress, Marketplace for items, and Gold for buy or sell gold posts.",
        inline=False,
    )
    embed.add_field(
        name="[MORE TOPICS]",
        value="!help verify | !help status | !help blackmarket | !help gold | !help sync | !help admin",
        inline=False,
    )
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


def project_hot_embed() -> discord.Embed:
    embed = make_embed(
        "VICTOR // PROJECTS // HOT",
        "Use this desk to file a project update without dragging the whole feature into chat. Pick a lane, answer a few short prompts, and Victor folds it into the right project bucket.",
        COLOR_NEUTRAL,
    )
    embed.add_field(name="[LANES]", value="Feature | Fix | Research | Archive", inline=False)
    embed.add_field(
        name="[FLOW]",
        value="Choose a lane, name the project, name the fold, add a short title, then drop the important details.",
        inline=False,
    )
    return embed


def project_update_created_embed(
    project_name: str,
    fold_key: str,
    update_type: str,
    title: str,
    update_id: int,
) -> discord.Embed:
    embed = make_embed(
        "VICTOR // PROJECTS",
        "[ UPDATE FILED ]\n\nProject note stored and folded where it belongs.",
        COLOR_OK,
    )
    embed.add_field(name="[PROJECT]", value=project_name, inline=True)
    embed.add_field(name="[FOLD]", value=fold_key, inline=True)
    embed.add_field(name="[TYPE]", value=update_type.upper(), inline=True)
    embed.add_field(name="[TITLE]", value=title, inline=False)
    embed.add_field(name="[FILE ID]", value=str(update_id), inline=True)
    return embed


def recent_project_updates_embed(updates: list) -> discord.Embed:
    embed = make_embed(
        "VICTOR // PROJECTS",
        "Recent project filings.",
        COLOR_NEUTRAL,
    )
    if not updates:
        embed.add_field(name="[UPDATES]", value="No project filings yet.", inline=False)
        return embed
    lines = []
    for row in updates[:6]:
        lines.append(
            f"#{row['id']} | {row['project_name']} | {row['fold_key']} | {row['update_type']} | {row['title']}"
        )
    embed.add_field(name="[RECENT]", value="```\n" + "\n".join(lines) + "\n```", inline=False)
    return embed
