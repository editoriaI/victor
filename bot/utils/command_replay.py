import logging
from typing import Optional

import discord
from sqlite3 import Connection

from bot import db
from bot.config import Config
from bot.utils.command_logging import log_system_event

COMMAND_HISTORY_LIMIT = 200
DETAILS_LIMIT = 5

logger = logging.getLogger("victor.replay")

async def scan_missed_commands(bot: discord.Client, cfg: Config) -> None:
    channel_ids = [channel_id for channel_id in cfg.command_watch_channel_ids if channel_id]
    if not channel_ids:
        return

    conn = db.get_connection(cfg.db_path)
    try:
        for channel_id in channel_ids:
            await _scan_channel(bot, cfg, conn, channel_id)
    finally:
        conn.close()


async def _scan_channel(bot: discord.Client, cfg: Config, conn: Connection, channel_id: int) -> None:
    if channel_id <= 0:
        return

    channel: Optional[discord.TextChannel] = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.HTTPException, discord.Forbidden, discord.NotFound):
            logger.debug("Could not fetch channel %s for command scan", channel_id)
            return

    if not isinstance(channel, discord.TextChannel):
        return

    last_id = db.fetch_command_watch_last(conn, channel_id)
    after = discord.Object(id=last_id) if last_id else None
    new_last_id = last_id
    commands = []
    async for message in channel.history(limit=COMMAND_HISTORY_LIMIT, oldest_first=True, after=after):
        new_last_id = max(new_last_id, message.id)
        if message.author.bot:
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

    lines = []
    for message, content in commands[:DETAILS_LIMIT]:
        timestamp = message.created_at.isoformat() if message.created_at else "unknown"
        summary = content.replace("\n", " ")
        lines.append(f"{timestamp} {message.author.display_name}: {summary}")

    details = (
        f"channel={channel_id} count={len(commands)} samples="
        f"{'; '.join(lines)[:1024]}"
    )
    await log_system_event(
        bot,
        cfg,
        "Missed Commands",
        details=details,
    )
