import logging
from datetime import datetime, timedelta, timezone
from sqlite3 import Connection
from typing import Optional

import discord
from discord.ext import commands

from bot import db
from bot.config import Config
from bot.utils.command_logging import log_system_event

COMMAND_HISTORY_LIMIT = 200
DETAILS_LIMIT = 5
FIRST_SCAN_LOOKBACK_HOURS = 24

logger = logging.getLogger("victor.replay")


async def scan_missed_commands(bot: discord.Client, cfg: Config) -> None:
    channels = await _collect_watch_channels(bot, cfg)
    if not channels:
        return

    conn = db.get_connection(cfg.db_path)
    try:
        for channel in channels:
            await _scan_channel(bot, cfg, conn, channel)
    finally:
        conn.close()


async def _collect_watch_channels(bot: discord.Client, cfg: Config) -> list[discord.TextChannel]:
    explicit_ids = [channel_id for channel_id in cfg.command_watch_channel_ids if channel_id]
    collected: dict[int, discord.TextChannel] = {}

    for channel_id in explicit_ids:
        channel = await _resolve_text_channel(bot, channel_id)
        if channel is not None:
            collected[channel.id] = channel

    if collected:
        return list(collected.values())

    for guild_id in cfg.command_guild_ids:
        guild = bot.get_guild(guild_id)
        if guild is None:
            try:
                guild = await bot.fetch_guild(guild_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                continue

        me = guild.me
        for channel in guild.text_channels:
            permissions = channel.permissions_for(me) if me else None
            if permissions and permissions.read_messages and permissions.read_message_history:
                collected[channel.id] = channel

    return list(collected.values())


async def _resolve_text_channel(bot: discord.Client, channel_id: int) -> Optional[discord.TextChannel]:
    if channel_id <= 0:
        return None

    channel: Optional[discord.TextChannel] = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.HTTPException, discord.Forbidden, discord.NotFound):
            logger.debug("Could not fetch channel %s for command scan", channel_id)
            return None

    if not isinstance(channel, discord.TextChannel):
        return None
    return channel


async def _scan_channel(
    bot: discord.Client,
    cfg: Config,
    conn: Connection,
    channel: discord.TextChannel,
) -> None:
    channel_id = channel.id
    last_id = db.fetch_command_watch_last(conn, channel_id)
    after = discord.Object(id=last_id) if last_id else None
    new_last_id = last_id
    commands = []
    first_scan_cutoff = datetime.now(timezone.utc) - timedelta(hours=FIRST_SCAN_LOOKBACK_HOURS)

    async for message in channel.history(limit=COMMAND_HISTORY_LIMIT, oldest_first=True, after=after):
        new_last_id = max(new_last_id, message.id)
        if message.author.bot:
            continue
        if not last_id and message.created_at and message.created_at < first_scan_cutoff:
            continue

        content = (message.content or "").strip()
        if not content.startswith(cfg.prefix):
            continue
        commands.append((message, content))

    if new_last_id and new_last_id != last_id:
        db.upsert_command_watch_last(conn, channel_id, new_last_id)
        conn.commit()

    if not commands:
        return

    newer_command_ids = _find_superseded_command_ids(commands)
    replayed = 0
    skipped = 0
    for message, content in commands:
        if await _should_skip_replay(bot, message, cfg, newer_command_ids):
            skipped += 1
            continue
        if await _replay_command(bot, message):
            replayed += 1
        else:
            skipped += 1

    lines = []
    for message, content in commands[:DETAILS_LIMIT]:
        timestamp = message.created_at.isoformat() if message.created_at else "unknown"
        summary = content.replace("\n", " ")
        lines.append(f"{timestamp} #{channel.name} {message.author.display_name}: {summary}")

    details = (
        f"channel={channel_id} name={channel.name} count={len(commands)} replayed={replayed} skipped={skipped} samples="
        f"{'; '.join(lines)[:1024]}"
    )
    await log_system_event(
        bot,
        cfg,
        "Missed Commands",
        details=details,
    )


def _find_superseded_command_ids(commands: list[tuple[discord.Message, str]]) -> set[int]:
    superseded: set[int] = set()
    latest_by_author: dict[int, int] = {}

    for message, _content in reversed(commands):
        author_id = message.author.id
        if author_id in latest_by_author:
            superseded.add(message.id)
            continue
        latest_by_author[author_id] = message.id

    return superseded


async def _should_skip_replay(
    bot: discord.Client,
    message: discord.Message,
    cfg: Config,
    superseded_command_ids: set[int],
) -> bool:
    if not isinstance(bot, commands.Bot):
        return True
    if not _command_name_from_content(message.content, cfg.prefix):
        return True
    if message.id in superseded_command_ids:
        return True
    if await _has_bot_follow_up(bot, message):
        return True
    return False


def _command_name_from_content(content: str, prefix: str) -> str:
    text = (content or "").strip()
    if not text.startswith(prefix):
        return ""
    body = text[len(prefix):].strip()
    if not body:
        return ""
    return body.split()[0].casefold()


async def _has_bot_follow_up(bot: discord.Client, message: discord.Message) -> bool:
    if not bot.user:
        return False
    window_end = message.created_at + timedelta(seconds=20) if message.created_at else None
    async for candidate in message.channel.history(limit=8, after=message, oldest_first=True):
        if window_end and candidate.created_at and candidate.created_at > window_end:
            break
        if candidate.author.id != bot.user.id:
            continue
        if candidate.reference and candidate.reference.message_id == message.id:
            return True
        return True
    return False


async def _replay_command(bot: discord.Client, message: discord.Message) -> bool:
    if not isinstance(bot, commands.Bot):
        return False
    ctx = await bot.get_context(message)
    if not ctx.valid or ctx.command is None:
        return False
    await bot.invoke(ctx)
    return True
