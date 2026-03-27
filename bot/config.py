import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

OWNER_ROLE_NAME = "@\u265b \uff28\uff22\uff29\uff23 \u265b"


@dataclass
class Config:
    prefix: str = "!"
    db_path: str = "db/victor.db"
    roles: Dict[str, List[str]] = field(default_factory=dict)
    required_tags: List[str] = field(default_factory=list)
    required_regex: List[str] = field(default_factory=list)
    forbidden_regex: List[str] = field(default_factory=list)
    require_username_in_bio: bool = True
    min_bio_length: int = 20
    max_bio_length: int = 500
    auto_restart_on_changes: bool = True
    watch_poll_interval: float = 1.0
    log_channel_id: Optional[int] = None
    verify_channel_id: Optional[int] = None
    welcome_channel_id: Optional[int] = None
    intro_user_ids: List[int] = field(default_factory=list)
    command_guild_ids: List[int] = field(default_factory=list)
    highrise_api_base_url: str = "https://webapi.highrise.game"
    highrise_api_key: Optional[str] = None
    verification_max_failures: int = 2


def _default_roles() -> Dict[str, List[str]]:
    return {
        "owner": [OWNER_ROLE_NAME],
        "admin": ["Victor Admin"],
        "founder": ["Founder"],
        "verifier": ["Verifier"],
        "verified_unlock": ["Buyer", "Seller", "Blackmarket"],
        "blackmarket": ["Blackmarket"],
        "seller": ["Seller"],
        "buyer": ["Buyer"],
    }


def load_config() -> Config:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_path = os.path.join(base_dir, "config", "config.json")
    example_path = os.path.join(base_dir, "config", "config.example.json")
    config_path = os.getenv("VICTOR_CONFIG", default_path)

    data: Dict[str, object] = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    elif os.path.exists(example_path):
        with open(example_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

    default_roles = _default_roles()
    configured_roles = data.get("roles") or {}
    roles = {key: list(configured_roles.get(key, value)) for key, value in default_roles.items()}
    for key, value in configured_roles.items():
        if key not in roles:
            roles[key] = list(value)

    log_channel_id = data.get("log_channel_id")
    if log_channel_id is not None:
        try:
            log_channel_id = int(log_channel_id)
        except (TypeError, ValueError):
            log_channel_id = None

    verify_channel_id = data.get("verify_channel_id")
    if verify_channel_id is not None:
        try:
            verify_channel_id = int(verify_channel_id)
        except (TypeError, ValueError):
            verify_channel_id = None

    welcome_channel_id = data.get("welcome_channel_id")
    if welcome_channel_id is not None:
        try:
            welcome_channel_id = int(welcome_channel_id)
        except (TypeError, ValueError):
            welcome_channel_id = None

    intro_user_ids: List[int] = []
    for value in list(data.get("intro_user_ids", [])):
        try:
            intro_user_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    command_guild_ids: List[int] = []
    for value in list(data.get("command_guild_ids", [])):
        try:
            command_guild_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    return Config(
        prefix=str(data.get("prefix", "!")),
        db_path=str(data.get("db_path", "db/victor.db")),
        roles=roles,
        required_tags=list(data.get("required_tags", [])),
        required_regex=list(data.get("required_regex", [])),
        forbidden_regex=list(data.get("forbidden_regex", [])),
        require_username_in_bio=bool(data.get("require_username_in_bio", True)),
        min_bio_length=int(data.get("min_bio_length", 20)),
        max_bio_length=int(data.get("max_bio_length", 500)),
        auto_restart_on_changes=bool(data.get("auto_restart_on_changes", True)),
        watch_poll_interval=float(data.get("watch_poll_interval", 1.0)),
        log_channel_id=log_channel_id,
        verify_channel_id=verify_channel_id,
        welcome_channel_id=welcome_channel_id,
        intro_user_ids=intro_user_ids,
        command_guild_ids=command_guild_ids,
        highrise_api_base_url=str(data.get("highrise_api_base_url", "https://webapi.highrise.game")).rstrip("/"),
        highrise_api_key=os.getenv("HIGHRISE_API_KEY") or data.get("highrise_api_key"),
        verification_max_failures=int(data.get("verification_max_failures", 2)),
    )
