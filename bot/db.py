import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _absolute_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, path)


def get_connection(db_path: str) -> sqlite3.Connection:
    abs_path = _absolute_path(db_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    conn = sqlite3.connect(abs_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(base_dir, "db", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as handle:
        schema_sql = handle.read()
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    if column_name in _table_columns(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _run_migrations(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "users", "highrise_user_id", "TEXT")
    _ensure_column(conn, "verification_codes", "highrise_user_id", "TEXT")
    _ensure_column(conn, "verification_codes", "highrise_username", "TEXT")
    _ensure_column(conn, "verification_codes", "fail_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "verification_codes", "last_error", "TEXT")
    _ensure_column(conn, "verification_codes", "verified_at", "TEXT")
    conn.execute(
        "UPDATE verification_codes SET highrise_username = '' WHERE highrise_username IS NULL"
    )


def upsert_user(
    conn: sqlite3.Connection,
    discord_id: str,
    highrise_username: str,
    linked: int,
    highrise_user_id: Optional[str] = None,
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO users (discord_id, highrise_user_id, highrise_username, linked, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
          highrise_user_id = excluded.highrise_user_id,
          highrise_username = excluded.highrise_username,
          linked = excluded.linked,
          updated_at = excluded.updated_at
        """,
        (discord_id, highrise_user_id, highrise_username, linked, now, now),
    )
    row = conn.execute("SELECT id FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
    return int(row["id"])


def record_verification(
    conn: sqlite3.Connection,
    user_id: int,
    verifier_id: str,
    bio_text: str,
    result: str,
    missing_tags: list,
    missing_regex: list,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO verifications (user_id, verifier_id, bio_text, result, missing_tags, missing_regex, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            verifier_id,
            bio_text,
            result,
            json.dumps(missing_tags),
            json.dumps(missing_regex),
            now,
        ),
    )


def upsert_verification_code(
    conn: sqlite3.Connection,
    user_id: int,
    highrise_user_id: Optional[str],
    highrise_username: str,
    code: str,
    status: str = "PENDING",
) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO verification_codes (
          user_id,
          highrise_user_id,
          highrise_username,
          code,
          status,
          fail_count,
          last_error,
          created_at,
          updated_at,
          verified_at
        )
        VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?, NULL)
        ON CONFLICT(user_id) DO UPDATE SET
          highrise_user_id = excluded.highrise_user_id,
          highrise_username = excluded.highrise_username,
          code = excluded.code,
          status = excluded.status,
          fail_count = 0,
          last_error = NULL,
          updated_at = excluded.updated_at
        """,
        (user_id, highrise_user_id, highrise_username, code, status, now, now),
    )


def queue_verification_review(
    conn: sqlite3.Connection,
    user_id: int,
    highrise_username: str,
    *,
    code: str = "SELF-REPORTED",
    highrise_user_id: Optional[str] = None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO verification_codes (
          user_id,
          highrise_user_id,
          highrise_username,
          code,
          status,
          fail_count,
          last_error,
          created_at,
          updated_at,
          verified_at
        )
        VALUES (?, ?, ?, ?, 'PENDING', 0, NULL, ?, ?, NULL)
        ON CONFLICT(user_id) DO UPDATE SET
          highrise_user_id = excluded.highrise_user_id,
          highrise_username = excluded.highrise_username,
          code = excluded.code,
          status = 'PENDING',
          fail_count = 0,
          last_error = NULL,
          updated_at = excluded.updated_at,
          verified_at = NULL
        """,
        (user_id, highrise_user_id, highrise_username, code, now, now),
    )


def fetch_verification_code(conn: sqlite3.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM verification_codes WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def mark_verification_success(conn: sqlite3.Connection, user_id: int) -> None:
    now = _utc_now()
    conn.execute(
        """
        UPDATE verification_codes
        SET status = 'VERIFIED',
            fail_count = 0,
            last_error = NULL,
            updated_at = ?,
            verified_at = ?
        WHERE user_id = ?
        """,
        (now, now, user_id),
    )


def increment_verification_fail(conn: sqlite3.Connection, user_id: int, status: str, error_message: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(fail_count, 0) AS fail_count FROM verification_codes WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    fail_count = int(row["fail_count"]) + 1 if row else 1
    now = _utc_now()
    conn.execute(
        """
        UPDATE verification_codes
        SET fail_count = ?,
            status = ?,
            last_error = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (fail_count, status, error_message, now, user_id),
    )
    return fail_count


def set_verification_status(
    conn: sqlite3.Connection,
    user_id: int,
    status: str,
    *,
    error_message: Optional[str] = None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        UPDATE verification_codes
        SET status = ?,
            last_error = ?,
            updated_at = ?,
            verified_at = CASE WHEN ? = 'VERIFIED' THEN ? ELSE verified_at END
        WHERE user_id = ?
        """,
        (status, error_message, now, status, now, user_id),
    )


def clear_verification_error(conn: sqlite3.Connection, user_id: int) -> None:
    now = _utc_now()
    conn.execute(
        """
        UPDATE verification_codes
        SET status = 'PENDING',
            last_error = NULL,
            updated_at = ?
        WHERE user_id = ?
        """,
        (now, user_id),
    )


def log_audit(conn: sqlite3.Connection, actor_id: str, action: str, target_id: Optional[str], details: str) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO audit_logs (actor_id, action, target_id, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (actor_id, action, target_id, details, now),
    )


def is_blacklisted(conn: sqlite3.Connection, discord_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM blacklist WHERE discord_id = ?", (discord_id,)).fetchone()
    return dict(row) if row else None


def add_blacklist(conn: sqlite3.Connection, discord_id: str, reason: str) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO blacklist (discord_id, reason, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET reason = excluded.reason
        """,
        (discord_id, reason, now),
    )


def remove_blacklist(conn: sqlite3.Connection, discord_id: str) -> None:
    conn.execute("DELETE FROM blacklist WHERE discord_id = ?", (discord_id,))


def list_blacklist(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM blacklist ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def create_listing(conn: sqlite3.Connection, seller_id: str, item_name: str, price: int) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO listings (seller_id, item_name, price, status, created_at, updated_at)
        VALUES (?, ?, ?, 'OPEN', ?, ?)
        """,
        (seller_id, item_name, price, now, now),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def fetch_listing(conn: sqlite3.Connection, listing_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    return dict(row) if row else None


def list_listings(conn: sqlite3.Connection, item_query: Optional[str] = None, limit: int = 10) -> list:
    if item_query:
        pattern = f"%{item_query.lower()}%"
        rows = conn.execute(
            """
            SELECT * FROM listings
            WHERE status = 'OPEN' AND lower(item_name) LIKE ?
            ORDER BY id DESC LIMIT ?
            """,
            (pattern, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM listings WHERE status = 'OPEN' ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def close_listing(conn: sqlite3.Connection, listing_id: int) -> None:
    now = _utc_now()
    conn.execute(
        "UPDATE listings SET status = 'REMOVED', updated_at = ? WHERE id = ?", (now, listing_id)
    )


def create_request(conn: sqlite3.Connection, buyer_id: str, item_name: str, max_price: int) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO match_requests (buyer_id, item_name, max_price, status, created_at, updated_at)
        VALUES (?, ?, ?, 'OPEN', ?, ?)
        """,
        (buyer_id, item_name, max_price, now, now),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def fetch_request(conn: sqlite3.Connection, request_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM match_requests WHERE id = ?", (request_id,)).fetchone()
    return dict(row) if row else None


def update_request_status(conn: sqlite3.Connection, request_id: int, status: str) -> None:
    now = _utc_now()
    conn.execute(
        "UPDATE match_requests SET status = ?, updated_at = ? WHERE id = ?", (status, now, request_id)
    )


def find_matching_listings(conn: sqlite3.Connection, item_name: str, max_price: int) -> list:
    pattern = f"%{item_name.lower()}%"
    rows = conn.execute(
        """
        SELECT * FROM listings
        WHERE status = 'OPEN' AND price <= ? AND lower(item_name) LIKE ?
        ORDER BY price ASC
        """,
        (max_price, pattern),
    ).fetchall()
    return [dict(row) for row in rows]


def create_match(conn: sqlite3.Connection, request_id: int, seller_id: str) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO matches (request_id, seller_id, status, created_at, updated_at)
        VALUES (?, ?, 'PENDING', ?, ?)
        """,
        (request_id, seller_id, now, now),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def list_matches_for_request(conn: sqlite3.Connection, request_id: int, status: Optional[str] = None) -> list:
    if status:
        rows = conn.execute(
            "SELECT * FROM matches WHERE request_id = ? AND status = ?", (request_id, status)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM matches WHERE request_id = ?", (request_id,)).fetchall()
    return [dict(row) for row in rows]


def fetch_match(conn: sqlite3.Connection, match_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    return dict(row) if row else None


def update_match_status(conn: sqlite3.Connection, match_id: int, status: str) -> None:
    now = _utc_now()
    conn.execute("UPDATE matches SET status = ?, updated_at = ? WHERE id = ?", (status, now, match_id))


def list_matches_for_seller(conn: sqlite3.Connection, seller_id: str, status: Optional[str] = None) -> list:
    if status:
        rows = conn.execute(
            "SELECT * FROM matches WHERE seller_id = ? AND status = ?", (seller_id, status)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM matches WHERE seller_id = ?", (seller_id,)).fetchall()
    return [dict(row) for row in rows]


def close_matches_for_request(conn: sqlite3.Connection, request_id: int, exclude_match_id: Optional[int] = None) -> None:
    now = _utc_now()
    if exclude_match_id is not None:
        conn.execute(
            """
            UPDATE matches SET status = 'CLOSED', updated_at = ?
            WHERE request_id = ? AND id != ? AND status = 'PENDING'
            """,
            (now, request_id, exclude_match_id),
        )
    else:
        conn.execute(
            """
            UPDATE matches SET status = 'CLOSED', updated_at = ?
            WHERE request_id = ? AND status = 'PENDING'
            """,
            (now, request_id),
        )


def fetch_user_by_discord_id(conn: sqlite3.Connection, discord_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,)).fetchone()
    return dict(row) if row else None


def fetch_latest_verification(conn: sqlite3.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM verifications WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
    ).fetchone()
    return dict(row) if row else None
