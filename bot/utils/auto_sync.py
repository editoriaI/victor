import logging

from bot import db
from bot.config import Config
from bot.utils.command_logging import log_system_event
from bot.utils.command_sync import sync_application_commands

logger = logging.getLogger("victor.auto_sync")
AUTO_SYNC_FLAG = "autosync"

async def maybe_auto_sync(bot, cfg: Config) -> None:
    if not _is_enabled(cfg):
        return

    logger.info("Auto-sync enabled, refreshing slash tree")
    synced_count = await sync_application_commands(bot, cfg)
    await log_system_event(
        bot,
        cfg,
        "Auto Sync",
        details=f"synced={synced_count}",
    )


def _is_enabled(cfg: Config) -> bool:
    conn = db.get_connection(cfg.db_path)
    try:
        return db.get_feature_flag(conn, AUTO_SYNC_FLAG, "0") == "1"
    finally:
        conn.close()
