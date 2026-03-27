import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from bot.config import Config

STATUS_COLORS = {
    "success": 0x2E8B57,
    "fail": 0xB22222,
    "warn": 0xD4A017,
    "system": 0x5865F2,
}

SURFACE_LABELS = {
    "prefix": "typed command",
    "slash": "slash command",
}

STATUS_HANDLES = {
    "success": "🖤 @victor.intern posted",
    "fail": "🕸️ @victor.intern posted a crash-thread",
    "warn": "📟 @victor.intern posted a side-eye update",
    "system": "💿 @victor.intern updated his feed",
}

SYSTEM_CODES = {
    "Child Online": 1001,
    "Restart Requested": 1101,
    "Restart Complete": 1102,
}

COMMAND_CODES = {
    "verify": 11,
    "manualverify": 12,
    "status": 13,
    "help": 14,
    "restart": 15,
    "sync": 16,
    "blacklist": 17,
    "blackmarket": 18,
    "marketlist": 19,
    "marketadd": 20,
    "marketremove": 21,
    "request": 22,
    "cancel": 23,
    "cancelrequest": 24,
    "accept": 25,
    "decline": 26,
    "unknown": 99,
}

PATCH_NOTE_ID = "2026-03-26-verify-intake-refresh"


def _truncate(value: Optional[str], limit: int = 1024) -> Optional[str]:
    if not value:
        return None
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _patch_note_state_path() -> Path:
    return _project_root() / "logs" / "patch-note-state.json"


def _load_patch_note_state() -> dict:
    path = _patch_note_state_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_patch_note_state(state: dict) -> None:
    path = _patch_note_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _build_patch_note_embed() -> discord.Embed:
    embed = discord.Embed(
        title="patch notes // verify intake refresh",
        description="[ PATCH LOG ]\n\nVictor has deployed a quieter, tighter verify flow.\n\nNo more bio ritual.\nJust usernames, intake, and staff judgment.\n\nCleaner system. Fewer excuses.",
        color=STATUS_COLORS["system"],
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name="💿 @victor.intern dropped release notes")
    embed.set_footer(text="v i c t o r . s o c i a l // patch desk")
    embed.add_field(
        name="What Changed",
        value=(
            "- `verify` now opens a member intake prompt\n"
            "- members submit their HR username directly\n"
            "- staff approves or rejects before anything gets filed"
        ),
        inline=False,
    )
    embed.add_field(
        name="Menu Lane",
        value="the `menu` verify button now launches the intake flow directly instead of just showing help text.",
        inline=False,
    )
    embed.add_field(
        name="Status + Staff",
        value="`status` shows pending, returned, or logged. staff still has manual verify for corrections or overrides.",
        inline=False,
    )
    embed.add_field(
        name="Live Commands",
        value="`menu`, `help`, `verify`, `manualverify`, `status`, and `sync` are the active lanes right now.",
        inline=False,
    )
    return embed


def _format_location(location: Optional[str]) -> Optional[str]:
    if not location:
        return None
    if location == "dm":
        return "direct messages"
    return f"guild {location}"


def _command_label(surface: Optional[str], command_name: Optional[str]) -> str:
    if not command_name:
        return "something dramatic"
    if surface == "slash":
        return f"/{command_name}"
    return f"!{command_name}"


def _event_code(
    status: str,
    *,
    command_name: Optional[str] = None,
    surface: Optional[str] = None,
    system_title: Optional[str] = None,
) -> int:
    if status == "system":
        return SYSTEM_CODES.get(system_title or "", 1999)

    command_code = COMMAND_CODES.get((command_name or "").casefold(), COMMAND_CODES["unknown"])
    base = {
        ("success", "prefix"): 2000,
        ("success", "slash"): 2100,
        ("warn", "prefix"): 2200,
        ("warn", "slash"): 2300,
        ("fail", "prefix"): 2400,
        ("fail", "slash"): 2500,
    }.get((status, surface or "prefix"), 2900)
    return base + command_code


def _command_post_copy(status: str, surface: Optional[str], command_name: Optional[str]) -> str:
    command_label = _command_label(surface, command_name)
    surface_label = SURFACE_LABELS.get(surface or "", "command")

    if status == "success":
        return (
            f"just finished `{command_label}` through {surface_label}. "
            "paperwork survived. everyone stay calm."
        )
    if status == "fail":
        return (
            f"tried `{command_label}` and the universe responded with nonsense. "
            "i'm documenting the mess before anyone gaslights me."
        )
    if status == "warn":
        return (
            f"`{command_label}` got weird. not catastrophic yet, but i am absolutely judging the situation."
        )
    return f"small status post: `{command_label}` moved something behind the curtain."


def _system_post_copy(title: Optional[str], details: Optional[str]) -> str:
    lowered = (title or "system update").lower()
    if title == "Restart Requested":
        return "brb. shedding this mortal process and stepping into something less embarrassing."
    if title == "Restart Complete":
        return "back from the dead again. fresh process. same attitude."
    if title == "Child Online":
        return "clocked back in. still undead. still employed. somehow."
    if "restart" in lowered:
        return "brb. shedding this mortal process and stepping into a fresher one."
    if "sync" in lowered:
        return "just pushed the command list back into formation. bureaucracy remains my curse."
    if details:
        return f"{lowered}. posting receipts so nobody acts confused later."
    return f"{lowered}. yes, i am announcing it like a status update."


def _build_feed_embed(
    status: str,
    *,
    user_id: Optional[int] = None,
    command_name: Optional[str] = None,
    location: Optional[str] = None,
    details: Optional[str] = None,
    surface: Optional[str] = None,
    system_title: Optional[str] = None,
) -> discord.Embed:
    description = (
        _system_post_copy(system_title, details)
        if status == "system"
        else _command_post_copy(status, surface, command_name)
    )
    title = (
        f"feed // {system_title or 'system update'}"
        if status == "system"
        else f"feed // {_command_label(surface, command_name)}"
    )
    embed = discord.Embed(
        title=title,
        description=description,
        color=STATUS_COLORS.get(status, STATUS_COLORS["system"]),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=STATUS_HANDLES.get(status, STATUS_HANDLES["system"]))
    embed.set_footer(text="v i c t o r . s o c i a l // live from the underworld desk")

    embed.add_field(
        name="Code",
        value=_event_code(
            status,
            command_name=command_name,
            surface=surface,
            system_title=system_title,
        ),
        inline=True,
    )

    if system_title:
        embed.add_field(name="Mood", value=system_title, inline=False)
    else:
        state = {
            "success": "cleared",
            "warn": "watch it",
            "fail": "mod look required",
        }.get(status, "noted")
        embed.add_field(name="State", value=state, inline=True)

    if user_id is not None:
        embed.add_field(name="Tagged", value=f"<@{user_id}>", inline=True)

    if command_name:
        embed.add_field(name="Thread", value=_command_label(surface, command_name), inline=True)

    if location:
        embed.add_field(name="Where", value=_format_location(location), inline=True)

    if details:
        embed.add_field(name="Receipts", value=_truncate(details), inline=False)

    return embed


async def send_log_channel(
    bot: commands.Bot,
    cfg: Config,
    message: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
) -> bool:
    channel_id = cfg.log_channel_id
    if not channel_id:
        return False
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.HTTPException, discord.Forbidden, discord.NotFound):
            return False
    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        try:
            await channel.send(content=message, embed=embed, view=view)
            return True
        except (discord.HTTPException, discord.Forbidden):
            return False
    return False


def format_command_log(
    status: str,
    surface: str,
    user_id: int,
    command_name: str,
    location: Optional[str],
    details: Optional[str] = None,
) -> str:
    message = f"{surface} {status} | user={user_id} | command={command_name}"
    if location:
        message += f" | location={location}"
    if details:
        message += f" | details={details}"
    return message


async def log_command_event(
    bot: commands.Bot,
    cfg: Config,
    status: str,
    surface: str,
    user_id: int,
    command_name: str,
    location: Optional[str],
    details: Optional[str] = None,
    level: int = logging.INFO,
    publish_to_channel: bool = True,
) -> None:
    message = format_command_log(status, surface, user_id, command_name, location, details)
    logging.getLogger("victor.commands").log(level, message)
    if not publish_to_channel:
        return
    if status == "fail":
        from bot.cogs.staff_console import send_command_attention_post

        await send_command_attention_post(
            bot,
            cfg,
            user_id=user_id,
            command_name=command_name,
            location=location,
            details=details,
            surface=surface,
        )
        return
    embed = _build_feed_embed(
        status,
        user_id=user_id,
        command_name=command_name,
        location=location,
        details=details,
        surface=surface,
    )
    await send_log_channel(bot, cfg, message=None, embed=embed)


async def log_system_event(
    bot: commands.Bot,
    cfg: Config,
    title: str,
    details: Optional[str] = None,
    level: int = logging.INFO,
    publish_to_channel: bool = True,
) -> None:
    logging.getLogger("victor.system").log(level, "%s | %s", title, details or "")
    if not publish_to_channel:
        return
    embed = _build_feed_embed("system", details=details, system_title=title)
    await send_log_channel(bot, cfg, message=None, embed=embed)


async def maybe_publish_patch_note(bot: commands.Bot, cfg: Config) -> None:
    if not cfg.log_channel_id:
        return
    state = _load_patch_note_state()
    if state.get("last_patch_note_id") == PATCH_NOTE_ID:
        return
    sent = await send_log_channel(bot, cfg, embed=_build_patch_note_embed())
    if not sent:
        return
    _write_patch_note_state(
        {
            "last_patch_note_id": PATCH_NOTE_ID,
            "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
