import unicodedata
from typing import Iterable, Sequence

import discord

OWNER_ROLE_ALIASES = ("@\u265b \uff28\uff22\uff29\uff23 \u265b", "\u265b \uff28\uff22\uff29\uff23 \u265b")
TRUSTED_ROLE_KEYS = ("seller", "buyer")


def _subject_roles(subject: discord.Member | Iterable[discord.abc.Snowflake]) -> list[discord.abc.Snowflake]:
    if hasattr(subject, "roles"):
        return list(getattr(subject, "roles"))
    return list(subject)


def _subject_member_id(subject: discord.Member | Iterable[discord.abc.Snowflake]) -> str | None:
    if hasattr(subject, "id"):
        return str(getattr(subject, "id"))
    return None


def normalize_role_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.casefold().strip()
    if normalized.startswith("@"):
        normalized = normalized[1:].strip()
    return " ".join(normalized.split())


def has_any_role(
    subject: discord.Member | Iterable[discord.abc.Snowflake],
    role_names: Sequence[str],
) -> bool:
    roles = _subject_roles(subject)
    member_id = _subject_member_id(subject)
    expected_ids = {
        str(name).strip()
        for name in list(role_names) + list(OWNER_ROLE_ALIASES)
        if str(name).strip().isdigit()
    }
    if member_id and member_id in expected_ids:
        return True
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


def matched_role_names(
    subject: discord.Member | Iterable[discord.abc.Snowflake],
    role_names: Sequence[str],
    *,
    fallback_label: str | None = None,
) -> list[str]:
    roles = _subject_roles(subject)
    member_id = _subject_member_id(subject)
    expected_ids = {
        str(name).strip()
        for name in role_names
        if str(name).strip().isdigit()
    }
    normalized_expected = {
        normalize_role_name(name)
        for name in role_names
        if name and not str(name).strip().isdigit()
    }

    matches: list[str] = []
    seen: set[str] = set()
    for role in roles:
        role_id = str(getattr(role, "id", "")).strip()
        role_name = str(getattr(role, "name", "") or "").strip()
        if not role_name:
            continue
        normalized_role_name = normalize_role_name(role_name)
        if role_id in expected_ids or normalized_role_name in normalized_expected:
            if role_name not in seen:
                matches.append(role_name)
                seen.add(role_name)
    if member_id and member_id in expected_ids and fallback_label and fallback_label not in seen:
        matches.append(fallback_label)
    return matches


def classify_member_access(
    subject: discord.Member | Iterable[discord.abc.Snowflake],
    configured_roles: dict[str, Sequence[str]],
) -> tuple[str, list[str]]:
    owner_matches = matched_role_names(
        subject,
        list(configured_roles.get("owner", [])) + list(OWNER_ROLE_ALIASES),
        fallback_label="Owner",
    )
    if owner_matches:
        return "owner", owner_matches

    admin_matches = matched_role_names(subject, configured_roles.get("admin", []), fallback_label="Admin")
    if admin_matches:
        return "admin", admin_matches

    founder_matches = matched_role_names(subject, configured_roles.get("founder", []), fallback_label="Founder")
    if founder_matches:
        return "founder", founder_matches

    trusted_matches: list[str] = []
    for key in TRUSTED_ROLE_KEYS:
        for role_name in matched_role_names(subject, configured_roles.get(key, []), fallback_label=key.title()):
            if role_name not in trusted_matches:
                trusted_matches.append(role_name)
    if trusted_matches:
        return "trusted", trusted_matches

    member_matches = matched_role_names(subject, configured_roles.get("member", []), fallback_label="Member")
    if member_matches:
        return "member", member_matches

    return "member", ["Member"]
