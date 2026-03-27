import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from bot import embeds
from bot.config import load_config
from bot import db
from bot.utils.command_logging import log_command_event, log_system_event, maybe_publish_patch_note
from bot.utils.restart_notice import pop_restart_notice

RESTART_EXIT_CODE = 26
NETWORK_RETRY_BASE_DELAY = 5
NETWORK_RETRY_MAX_DELAY = 60

ANSI_RESET = "\033[0m"
ANSI_COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[37m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[41m",
}


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = ANSI_COLORS.get(record.levelno)
        if not color:
            return message
        return f"{color}{message}{ANSI_RESET}"


def _setup_logging() -> None:
    base_dir = _project_root()
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(ColorFormatter("%(levelname)s | %(name)s | %(message)s"))

    file_handler = RotatingFileHandler(
        logs_dir / "victor-child.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("discord").setLevel(logging.ERROR)
    logging.getLogger("discord.client").setLevel(logging.ERROR)
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)
    logging.getLogger("discord.http").setLevel(logging.ERROR)
    logging.getLogger("aiohttp").setLevel(logging.ERROR)


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _supervisor_lock_path() -> Path:
    return _project_root() / "logs" / "victor-supervisor.lock"


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # Windows can raise a generic OSError for stale or invalid PIDs.
        return False
    return True


def _acquire_supervisor_lock() -> Optional[int]:
    lock_path = _supervisor_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
            return os.getpid()
        except FileExistsError:
            try:
                raw_pid = lock_path.read_text(encoding="utf-8").strip()
                existing_pid = int(raw_pid)
            except (OSError, ValueError):
                existing_pid = 0

            if existing_pid and _is_process_running(existing_pid):
                logging.warning("Victor supervisor already running with pid %s", existing_pid)
                return None

            try:
                lock_path.unlink()
            except OSError:
                logging.warning("Could not remove stale Victor lock file at %s", lock_path)
                return None


def _release_supervisor_lock(lock_pid: Optional[int]) -> None:
    if lock_pid != os.getpid():
        return
    lock_path = _supervisor_lock_path()
    try:
        raw_pid = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if raw_pid != str(os.getpid()):
        return
    try:
        lock_path.unlink()
    except OSError:
        pass


def _iter_watch_files(base_dir: Path) -> list[Path]:
    watch_files: list[Path] = []
    watch_dirs = [base_dir / "bot", base_dir / "config"]
    watch_suffixes = {".py", ".json", ".sql"}
    watch_names = {".env", "requirements.txt"}

    for watch_dir in watch_dirs:
        if not watch_dir.exists():
            continue
        for path in watch_dir.rglob("*"):
            if path.is_file() and path.suffix in watch_suffixes:
                watch_files.append(path)

    for name in watch_names:
        path = base_dir / name
        if path.exists():
            watch_files.append(path)

    return sorted(set(watch_files))


def _snapshot_watch_files(base_dir: Path) -> dict[str, int]:
    snapshot: dict[str, int] = {}
    for path in _iter_watch_files(base_dir):
        try:
            snapshot[str(path)] = path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def _watch_for_code_changes(process: subprocess.Popen[bytes], cfg) -> bool:
    base_dir = _project_root()
    previous = _snapshot_watch_files(base_dir)
    poll_interval = max(0.5, float(cfg.watch_poll_interval))

    while process.poll() is None:
        time.sleep(poll_interval)
        current = _snapshot_watch_files(base_dir)
        if current != previous:
            changed = sorted(set(current.items()) ^ set(previous.items()))
            changed_path = changed[0][0] if changed else "project files"
            logging.warning("Code change detected in %s. Restarting Victor.", changed_path)
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return True
        previous = current

    return False


def _run_supervisor(cfg) -> int:
    base_dir = _project_root()
    child_env = os.environ.copy()
    child_env["VICTOR_CHILD"] = "1"

    while True:
        logging.info("Starting Victor child process")
        process = subprocess.Popen(
            [sys.executable, "-m", "bot.main"],
            cwd=str(base_dir),
            env=child_env,
        )
        logging.getLogger("victor.system").info("Supervisor spawned child | pid=%s", process.pid)

        changed = _watch_for_code_changes(process, cfg) if cfg.auto_restart_on_changes else False
        if changed:
            continue

        return_code = process.wait()
        logging.getLogger("victor.system").info("Child exited | pid=%s | return_code=%s", process.pid, return_code)
        if return_code == RESTART_EXIT_CODE:
            logging.info("Victor requested a restart. Relaunching.")
            logging.getLogger("victor.system").info("Supervisor relaunching child after restart request")
            continue
        return return_code


def _restart_child_process() -> None:
    base_dir = _project_root()
    child_env = os.environ.copy()
    child_env["VICTOR_CHILD"] = "1"
    creationflags = 0
    creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    popen_kwargs = {
        "cwd": str(base_dir),
        "env": child_env,
    }
    if creationflags:
        popen_kwargs["creationflags"] = creationflags
    process = subprocess.Popen([sys.executable, "-m", "bot.main"], **popen_kwargs)
    logging.getLogger("victor.system").info(
        "Child restart spawned replacement | pid=%s | cwd=%s",
        process.pid,
        base_dir,
    )


def create_bot(cfg) -> commands.Bot:
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = commands.Bot(command_prefix=cfg.prefix, intents=intents, help_command=None)
    bot.victor_config = cfg
    bot.victor_restart_requested = False

    @bot.event
    async def on_ready() -> None:
        logging.info("Victor online as %s", bot.user)
        await log_system_event(
            bot,
            cfg,
            "Child Online",
            details=f"user={bot.user} | synced={getattr(bot, 'victor_synced_count', 'unknown')}",
            publish_to_channel=False,
        )
        restart_notice = pop_restart_notice()
        if restart_notice:
            await log_system_event(
                bot,
                cfg,
                "Restart Complete",
                details=(
                    f"actor={restart_notice.get('actor_id')} | "
                    f"guild={restart_notice.get('guild_id') or 'dm'} | "
                    f"surface={restart_notice.get('surface')}"
                ),
            )
        await maybe_publish_patch_note(bot, cfg)

    @bot.event
    async def on_member_join(member: discord.Member) -> None:
        verify_channel_id = cfg.verify_channel_id
        if not verify_channel_id:
            return

        verify_channel_mention = f"<#{verify_channel_id}>"
        embed = embeds.verify_join_embed(member.mention, verify_channel_mention)

        try:
            await member.send(embed=embed)
        except discord.HTTPException:
            logging.getLogger("victor.verify").info("Could not DM verify onboarding to %s", member.id)

        welcome_channel_id = cfg.welcome_channel_id
        if not welcome_channel_id:
            return

        channel = bot.get_channel(welcome_channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(welcome_channel_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                return

        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(content=member.mention, embed=embed)
            except (discord.HTTPException, discord.Forbidden):
                return

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        if bot.user and bot.user in message.mentions and not message.content.strip().startswith(cfg.prefix):
            verify_channel_mention = f"<#{cfg.verify_channel_id}>" if cfg.verify_channel_id else None
            try:
                async with message.channel.typing():
                    await asyncio.sleep(1.4)
                await message.reply(
                    embed=embeds.victor_intro_embed(message.author.mention, verify_channel_mention),
                    mention_author=False,
                )
            except (discord.HTTPException, discord.Forbidden):
                pass

        await bot.process_commands(message)

    @bot.event
    async def on_app_command_completion(
        interaction: discord.Interaction, command: discord.app_commands.Command
    ) -> None:
        await log_command_event(
            bot,
            cfg,
            "success",
            "slash",
            interaction.user.id,
            command.qualified_name,
            str(interaction.guild_id) if interaction.guild_id else "dm",
            publish_to_channel=False,
        )

    @bot.event
    async def setup_hook() -> None:
        # Bring verify and help back online while the rest of the broader command set stays parked.
        await bot.load_extension("bot.cogs.staff_console")
        await bot.load_extension("bot.cogs.monitor")
        await bot.load_extension("bot.cogs.verify")
        await bot.load_extension("bot.cogs.admin")
        await bot.load_extension("bot.cogs.help")
        synced = await bot.tree.sync()
        bot.victor_synced_count = len(synced)
        logging.info("Synced %s application commands", len(synced))

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        await log_command_event(
            bot,
            cfg,
            "fail",
            "slash",
            interaction.user.id,
            interaction.command.qualified_name if interaction.command else "unknown",
            str(interaction.guild_id) if interaction.guild_id else "dm",
            details=str(error),
            level=logging.ERROR,
        )
        logging.exception(
            "Slash command failed: %s",
            interaction.command.qualified_name if interaction.command else "unknown",
            exc_info=getattr(error, "original", error),
        )
        embed = embeds.system_error_embed()
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.NotFound):
            return

    return bot


def _run_bot_with_retries(cfg, token: str) -> commands.Bot:
    attempt = 0

    while True:
        bot = create_bot(cfg)
        try:
            bot.run(token)
            return bot
        except (aiohttp.ClientError, TimeoutError, discord.GatewayNotFound) as exc:
            attempt += 1
            delay = min(NETWORK_RETRY_MAX_DELAY, NETWORK_RETRY_BASE_DELAY * attempt)
            logging.warning(
                "Discord connection failed during startup (%s). Retrying in %ss.",
                exc.__class__.__name__,
                delay,
            )
            logging.getLogger("victor.system").warning(
                "Discord startup retry scheduled | attempt=%s | delay=%ss | error=%s",
                attempt,
                delay,
                exc.__class__.__name__,
            )
            time.sleep(delay)


def main() -> None:
    _setup_logging()
    _load_dotenv()
    cfg = load_config()
    lock_pid: Optional[int] = None

    if os.getenv("VICTOR_CHILD") != "1":
        lock_pid = _acquire_supervisor_lock()
        if lock_pid is None:
            raise SystemExit(0)
    try:
        if os.getenv("VICTOR_CHILD") != "1" and cfg.auto_restart_on_changes:
            raise SystemExit(_run_supervisor(cfg))

        db.init_db(cfg.db_path)

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("DISCORD_TOKEN is not set")

        bot = _run_bot_with_retries(cfg, token)
        if getattr(bot, "victor_restart_requested", False):
            logging.getLogger("victor.system").info(
                "Restart handoff reached main loop | child_mode=%s",
                os.getenv("VICTOR_CHILD") == "1",
            )
            if os.getenv("VICTOR_CHILD") == "1":
                _restart_child_process()
                raise SystemExit(0)
            raise SystemExit(RESTART_EXIT_CODE)
    finally:
        _release_supervisor_lock(lock_pid)


if __name__ == "__main__":
    main()
