import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _notice_path() -> Path:
    path = _project_root() / "logs" / "restart-notice.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_restart_notice(actor_id: int, guild_id: Optional[int], surface: str) -> None:
    payload = {
        "actor_id": actor_id,
        "guild_id": guild_id,
        "surface": surface,
        "created_at": datetime.now(timezone.utc).timestamp(),
    }
    _notice_path().write_text(json.dumps(payload), encoding="utf-8")


def pop_restart_notice(max_age_seconds: int = 300) -> Optional[dict]:
    path = _notice_path()
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        try:
            path.unlink()
        except OSError:
            pass
        return None

    try:
        created_at = float(payload.get("created_at", 0))
    except (TypeError, ValueError):
        created_at = 0

    age = datetime.now(timezone.utc).timestamp() - created_at
    try:
        path.unlink()
    except OSError:
        pass

    if age < 0 or age > max_age_seconds:
        return None
    return payload
