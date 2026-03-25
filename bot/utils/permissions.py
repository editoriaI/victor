import unicodedata
from typing import Iterable, Sequence

import discord

OWNER_ROLE_ALIASES = ("@\u265b \uff28\uff22\uff29\uff23 \u265b", "\u265b \uff28\uff22\uff29\uff23 \u265b")


def normalize_role_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.casefold().strip()
    if normalized.startswith("@"):
        normalized = normalized[1:].strip()
    return " ".join(normalized.split())


def has_any_role(roles: Iterable[discord.abc.Snowflake], role_names: Sequence[str]) -> bool:
    expected_ids = {
        str(name).strip()
        for name in list(role_names) + list(OWNER_ROLE_ALIASES)
        if str(name).strip().isdigit()
    }
    member_ids = {
        str(getattr(role, "id"))
        for role in roles
        if getattr(role, "id", None) is not None
    }
    if member_ids & expected_ids:
        return True

    normalized_member_roles = {
        normalize_role_name(getattr(role, "name", ""))
        for role in roles
        if getattr(role, "name", None)
    }
    normalized_expected = {
        normalize_role_name(name)
        for name in list(role_names) + list(OWNER_ROLE_ALIASES)
        if name
    }
    return bool(normalized_member_roles & normalized_expected)
