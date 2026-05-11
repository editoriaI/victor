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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS command_watch (
          channel_id INTEGER PRIMARY KEY,
          last_message_id INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_flags (
          name TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS member_role_snapshots (
          guild_id TEXT NOT NULL,
          user_id INTEGER NOT NULL,
          discord_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          primary_role TEXT NOT NULL,
          matched_roles TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (guild_id, discord_id),
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    _ensure_column(conn, "member_role_snapshots", "user_id", "INTEGER")
    conn.execute(
        """
        UPDATE member_role_snapshots
        SET user_id = (
          SELECT users.id
          FROM users
          WHERE users.discord_id = member_role_snapshots.discord_id
        )
        WHERE user_id IS NULL
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS linked_accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL UNIQUE,
          discord_id TEXT NOT NULL,
          guild_id TEXT,
          highrise_user_id TEXT,
          highrise_username TEXT,
          verification_status TEXT NOT NULL DEFAULT 'UNLINKED',
          verified_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bank_accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          account_key TEXT NOT NULL UNIQUE,
          user_id INTEGER,
          discord_id TEXT,
          account_type TEXT NOT NULL,
          asset_type TEXT NOT NULL DEFAULT 'gold',
          status TEXT NOT NULL DEFAULT 'OPEN',
          balance INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS banking_transactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          transaction_key TEXT NOT NULL UNIQUE,
          transaction_type TEXT NOT NULL,
          status TEXT NOT NULL,
          asset_type TEXT NOT NULL DEFAULT 'gold',
          amount INTEGER NOT NULL,
          actor_id TEXT,
          source_system TEXT NOT NULL,
          idempotency_key TEXT,
          reference_type TEXT,
          reference_id TEXT,
          metadata TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          finalized_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger_entries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          transaction_id INTEGER NOT NULL,
          account_id INTEGER NOT NULL,
          user_id INTEGER,
          discord_id TEXT,
          entry_kind TEXT NOT NULL,
          amount INTEGER NOT NULL,
          balance_after INTEGER NOT NULL,
          note TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY(transaction_id) REFERENCES banking_transactions(id),
          FOREIGN KEY(account_id) REFERENCES bank_accounts(id),
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS treasury_snapshots (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_wallet_balance INTEGER NOT NULL,
          ledger_treasury_balance INTEGER NOT NULL,
          total_user_liabilities INTEGER NOT NULL,
          total_savings_liabilities INTEGER NOT NULL,
          total_checking_liabilities INTEGER NOT NULL,
          total_pending_withdrawals INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          details TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_key TEXT NOT NULL UNIQUE,
          project_name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'ACTIVE',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_posts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          discord_id TEXT NOT NULL,
          guild_id TEXT,
          channel_id TEXT NOT NULL,
          action TEXT NOT NULL,
          asset_type TEXT NOT NULL DEFAULT 'gold',
          item_name TEXT NOT NULL,
          price INTEGER NOT NULL,
          details TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'OPEN',
          trusted_boost INTEGER NOT NULL DEFAULT 0,
          bump_count INTEGER NOT NULL DEFAULT 0,
          source_post_id TEXT,
          expires_at TEXT,
          last_bumped_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_updates (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id INTEGER NOT NULL,
          fold_key TEXT NOT NULL,
          update_type TEXT NOT NULL,
          title TEXT NOT NULL,
          details TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vouches (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_message_id TEXT NOT NULL UNIQUE,
          guild_id TEXT,
          channel_id TEXT NOT NULL,
          subject_discord_id TEXT NOT NULL,
          voucher_discord_id TEXT,
          details TEXT NOT NULL,
          source_url TEXT,
          created_at TEXT NOT NULL,
          imported_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_linked_accounts_discord_id ON linked_accounts(discord_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bank_accounts_user_type ON bank_accounts(user_id, account_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_banking_transactions_actor_id ON banking_transactions(actor_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_banking_transactions_reference ON banking_transactions(reference_type, reference_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ledger_entries_transaction_id ON ledger_entries(transaction_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ledger_entries_account_id ON ledger_entries(account_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_market_posts_lookup ON market_posts(asset_type, action, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_updates_project_id ON project_updates(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_vouches_subject_discord_id ON vouches(subject_discord_id)"
    )
    conn.execute(
        """
        INSERT INTO linked_accounts (
          user_id,
          discord_id,
          highrise_user_id,
          highrise_username,
          verification_status,
          verified_at,
          created_at,
          updated_at
        )
        SELECT
          users.id,
          users.discord_id,
          users.highrise_user_id,
          users.highrise_username,
          CASE WHEN users.linked = 1 THEN 'VERIFIED' ELSE 'UNLINKED' END,
          verification_codes.verified_at,
          users.created_at,
          users.updated_at
        FROM users
        LEFT JOIN verification_codes ON verification_codes.user_id = users.id
        WHERE NOT EXISTS (
          SELECT 1 FROM linked_accounts WHERE linked_accounts.user_id = users.id
        )
        """
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
    user_id = int(row["id"])
    upsert_linked_account(
        conn,
        user_id=user_id,
        discord_id=discord_id,
        highrise_user_id=highrise_user_id,
        highrise_username=highrise_username,
        verification_status="VERIFIED" if linked else "UNLINKED",
    )
    return user_id


def upsert_linked_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    discord_id: str,
    guild_id: Optional[str] = None,
    highrise_user_id: Optional[str] = None,
    highrise_username: Optional[str] = None,
    verification_status: str = "UNLINKED",
    verified_at: Optional[str] = None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO linked_accounts (
          user_id,
          discord_id,
          guild_id,
          highrise_user_id,
          highrise_username,
          verification_status,
          verified_at,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          discord_id = excluded.discord_id,
          guild_id = COALESCE(excluded.guild_id, linked_accounts.guild_id),
          highrise_user_id = COALESCE(excluded.highrise_user_id, linked_accounts.highrise_user_id),
          highrise_username = COALESCE(excluded.highrise_username, linked_accounts.highrise_username),
          verification_status = excluded.verification_status,
          verified_at = COALESCE(excluded.verified_at, linked_accounts.verified_at),
          updated_at = excluded.updated_at
        """,
        (
            user_id,
            discord_id,
            guild_id,
            highrise_user_id,
            highrise_username,
            verification_status,
            verified_at,
            now,
            now,
        ),
    )


def fetch_linked_account_by_discord_id(conn: sqlite3.Connection, discord_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT linked_accounts.*, users.linked
        FROM linked_accounts
        INNER JOIN users ON users.id = linked_accounts.user_id
        WHERE linked_accounts.discord_id = ?
        """,
        (discord_id,),
    ).fetchone()
    return dict(row) if row else None


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
    conn.execute(
        "UPDATE users SET linked = 1, updated_at = ? WHERE id = ?",
        (now, user_id),
    )
    conn.execute(
        """
        UPDATE linked_accounts
        SET verification_status = 'VERIFIED',
            verified_at = ?,
            updated_at = ?
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
    linked_flag = 1 if status == "VERIFIED" else 0
    conn.execute(
        "UPDATE users SET linked = ?, updated_at = ? WHERE id = ?",
        (linked_flag, now, user_id),
    )
    conn.execute(
        """
        UPDATE linked_accounts
        SET verification_status = ?,
            verified_at = CASE WHEN ? = 'VERIFIED' THEN ? ELSE verified_at END,
            updated_at = ?
        WHERE user_id = ?
        """,
        (status, status, now, now, user_id),
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


def upsert_member_role_snapshot(
    conn: sqlite3.Connection,
    guild_id: str,
    user_id: int,
    discord_id: str,
    display_name: str,
    primary_role: str,
    matched_roles: list[str],
) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO member_role_snapshots (
          guild_id,
          user_id,
          discord_id,
          display_name,
          primary_role,
          matched_roles,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, discord_id) DO UPDATE SET
          user_id = excluded.user_id,
          display_name = excluded.display_name,
          primary_role = excluded.primary_role,
          matched_roles = excluded.matched_roles,
          updated_at = excluded.updated_at
        """,
        (
            guild_id,
            user_id,
            discord_id,
            display_name,
            primary_role,
            json.dumps(matched_roles),
            now,
            now,
        ),
    )


def remove_member_role_snapshot(conn: sqlite3.Connection, guild_id: str, discord_id: str) -> None:
    conn.execute(
        "DELETE FROM member_role_snapshots WHERE guild_id = ? AND discord_id = ?",
        (guild_id, discord_id),
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


def create_market_post(
    conn: sqlite3.Connection,
    *,
    discord_id: str,
    guild_id: Optional[str],
    channel_id: str,
    action: str,
    asset_type: str,
    item_name: str,
    price: int,
    details: str,
    trusted_boost: bool = False,
    source_post_id: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO market_posts (
          discord_id,
          guild_id,
          channel_id,
          action,
          asset_type,
          item_name,
          price,
          details,
          status,
          trusted_boost,
          bump_count,
          source_post_id,
          expires_at,
          last_bumped_at,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, 0, ?, ?, NULL, ?, ?)
        """,
        (
            discord_id,
            guild_id,
            channel_id,
            action,
            asset_type,
            item_name,
            price,
            details,
            1 if trusted_boost else 0,
            source_post_id,
            expires_at,
            now,
            now,
        ),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def list_active_market_posts(
    conn: sqlite3.Connection,
    *,
    asset_type: Optional[str] = None,
    action: Optional[str] = None,
    discord_id: Optional[str] = None,
    item_name: Optional[str] = None,
    limit: int = 20,
) -> list:
    clauses = ["status = 'OPEN'"]
    params: list[Any] = []
    if asset_type:
        clauses.append("asset_type = ?")
        params.append(asset_type)
    if action:
        clauses.append("action = ?")
        params.append(action)
    if discord_id:
        clauses.append("discord_id = ?")
        params.append(discord_id)
    if item_name:
        clauses.append("lower(item_name) = ?")
        params.append(item_name.lower())
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT * FROM market_posts
        WHERE {' AND '.join(clauses)}
        ORDER BY id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def list_market_posts_by_signature(
    conn: sqlite3.Connection,
    *,
    discord_id: str,
    asset_type: str,
    action: str,
    item_name: str,
    price: int,
    details: str,
    statuses: Optional[list[str]] = None,
    limit: int = 10,
) -> list:
    clauses = [
        "discord_id = ?",
        "asset_type = ?",
        "action = ?",
        "item_name = ?",
        "price = ?",
        "details = ?",
    ]
    params: list[Any] = [discord_id, asset_type, action, item_name, price, details]
    active_statuses = statuses or ["OPEN", "BUMPED"]
    placeholders = ", ".join("?" for _ in active_statuses)
    clauses.append(f"status IN ({placeholders})")
    params.extend(active_statuses)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT * FROM market_posts
        WHERE {' AND '.join(clauses)}
        ORDER BY id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_latest_market_post(
    conn: sqlite3.Connection,
    *,
    discord_id: str,
    asset_type: Optional[str] = None,
    statuses: Optional[list[str]] = None,
) -> Optional[Dict[str, Any]]:
    clauses = ["discord_id = ?"]
    params: list[Any] = [discord_id]
    if asset_type:
        clauses.append("asset_type = ?")
        params.append(asset_type)
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        clauses.append(f"status IN ({placeholders})")
        params.extend(statuses)
    row = conn.execute(
        f"""
        SELECT * FROM market_posts
        WHERE {' AND '.join(clauses)}
        ORDER BY id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    return dict(row) if row else None


def find_market_post_cooldown(
    conn: sqlite3.Connection,
    *,
    discord_id: str,
    asset_type: str,
    action: str,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT * FROM market_posts
        WHERE discord_id = ? AND asset_type = ? AND action = ? AND status IN ('OPEN', 'BUMPED')
        ORDER BY id DESC
        LIMIT 1
        """,
        (discord_id, asset_type, action),
    ).fetchone()
    return dict(row) if row else None


def find_market_matches(
    conn: sqlite3.Connection,
    *,
    asset_type: str,
    opposite_action: str,
    item_name: str,
    price: int,
    exclude_discord_id: Optional[str] = None,
    limit: int = 5,
) -> list:
    clauses = [
        "status IN ('OPEN', 'BUMPED')",
        "asset_type = ?",
        "action = ?",
        "lower(item_name) = ?",
    ]
    params: list[Any] = [asset_type, opposite_action, item_name.lower()]
    if exclude_discord_id:
        clauses.append("discord_id != ?")
        params.append(exclude_discord_id)

    if opposite_action == "sell":
        clauses.append("price <= ?")
    else:
        clauses.append("price >= ?")
    params.append(price)
    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT * FROM market_posts
        WHERE {' AND '.join(clauses)}
        ORDER BY id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def list_expired_market_posts(conn: sqlite3.Connection, now_iso: str, limit: int = 25) -> list:
    rows = conn.execute(
        """
        SELECT * FROM market_posts
        WHERE status IN ('OPEN', 'BUMPED') AND expires_at IS NOT NULL AND expires_at <= ?
        ORDER BY expires_at ASC
        LIMIT ?
        """,
        (now_iso, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def bump_market_post(conn: sqlite3.Connection, post_id: int, *, expires_at: Optional[str]) -> None:
    now = _utc_now()
    conn.execute(
        """
        UPDATE market_posts
        SET status = 'BUMPED',
            bump_count = bump_count + 1,
            last_bumped_at = ?,
            expires_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, expires_at, now, post_id),
    )


def close_market_post(conn: sqlite3.Connection, post_id: int, *, status: str = "EXPIRED") -> None:
    now = _utc_now()
    conn.execute(
        "UPDATE market_posts SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, post_id),
    )


def fetch_command_watch_last(conn: sqlite3.Connection, channel_id: int) -> int:
    row = conn.execute("SELECT last_message_id FROM command_watch WHERE channel_id = ?", (channel_id,)).fetchone()
    return int(row["last_message_id"]) if row else 0


def upsert_command_watch_last(conn: sqlite3.Connection, channel_id: int, last_message_id: int) -> None:
  conn.execute(
        """
        INSERT INTO command_watch (channel_id, last_message_id)
        VALUES (?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
          last_message_id = excluded.last_message_id
        """,
      (channel_id, last_message_id),
    )


def get_feature_flag(conn: sqlite3.Connection, name: str, default: str = "0") -> str:
    row = conn.execute("SELECT value FROM feature_flags WHERE name = ?", (name,)).fetchone()
    return str(row["value"]) if row else default


def set_feature_flag(conn: sqlite3.Connection, name: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO feature_flags (name, value)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET
          value = excluded.value
        """,
        (name, value),
    )


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


def fetch_bank_account(
    conn: sqlite3.Connection,
    *,
    user_id: Optional[int] = None,
    discord_id: Optional[str] = None,
    account_type: str,
) -> Optional[Dict[str, Any]]:
    if user_id is not None:
        row = conn.execute(
            """
            SELECT * FROM bank_accounts
            WHERE user_id = ? AND account_type = ? AND status = 'OPEN'
            LIMIT 1
            """,
            (user_id, account_type),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM bank_accounts
            WHERE discord_id = ? AND account_type = ? AND status = 'OPEN'
            LIMIT 1
            """,
            (discord_id, account_type),
        ).fetchone()
    return dict(row) if row else None


def ensure_member_bank_accounts(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    discord_id: str,
) -> Dict[str, Dict[str, Any]]:
    accounts: Dict[str, Dict[str, Any]] = {}
    for account_type in ("checking", "savings"):
        account = fetch_bank_account(conn, user_id=user_id, account_type=account_type)
        if account is None:
            create_bank_account(
                conn,
                account_key=f"user:{discord_id}:{account_type}",
                user_id=user_id,
                discord_id=discord_id,
                account_type=account_type,
            )
            account = fetch_bank_account(conn, user_id=user_id, account_type=account_type)
        if account is not None:
            accounts[account_type] = account
    return accounts


def create_bank_account(
    conn: sqlite3.Connection,
    *,
    account_key: str,
    user_id: Optional[int],
    discord_id: Optional[str],
    account_type: str,
    asset_type: str = "gold",
    balance: int = 0,
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO bank_accounts (
          account_key,
          user_id,
          discord_id,
          account_type,
          asset_type,
          status,
          balance,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
        """,
        (account_key, user_id, discord_id, account_type, asset_type, balance, now, now),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def update_bank_account_balance(conn: sqlite3.Connection, account_id: int, balance: int) -> None:
    now = _utc_now()
    conn.execute(
        "UPDATE bank_accounts SET balance = ?, updated_at = ? WHERE id = ?",
        (balance, now, account_id),
    )


def create_banking_transaction(
    conn: sqlite3.Connection,
    *,
    transaction_key: str,
    transaction_type: str,
    status: str,
    amount: int,
    actor_id: Optional[str],
    source_system: str,
    asset_type: str = "gold",
    idempotency_key: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO banking_transactions (
          transaction_key,
          transaction_type,
          status,
          asset_type,
          amount,
          actor_id,
          source_system,
          idempotency_key,
          reference_type,
          reference_id,
          metadata,
          created_at,
          finalized_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_key,
            transaction_type,
            status,
            asset_type,
            amount,
            actor_id,
            source_system,
            idempotency_key,
            reference_type,
            reference_id,
            json.dumps(metadata or {}),
            now,
            now if status == "COMPLETED" else None,
        ),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def update_banking_transaction_status(conn: sqlite3.Connection, transaction_id: int, status: str) -> None:
    now = _utc_now()
    conn.execute(
        """
        UPDATE banking_transactions
        SET status = ?, finalized_at = CASE WHEN ? = 'COMPLETED' THEN ? ELSE finalized_at END
        WHERE id = ?
        """,
        (status, status, now, transaction_id),
    )


def create_ledger_entry(
    conn: sqlite3.Connection,
    *,
    transaction_id: int,
    account_id: int,
    user_id: Optional[int],
    discord_id: Optional[str],
    entry_kind: str,
    amount: int,
    balance_after: int,
    note: Optional[str] = None,
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO ledger_entries (
          transaction_id,
          account_id,
          user_id,
          discord_id,
          entry_kind,
          amount,
          balance_after,
          note,
          created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (transaction_id, account_id, user_id, discord_id, entry_kind, amount, balance_after, note, now),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def list_recent_banking_transactions_for_user(
    conn: sqlite3.Connection,
    discord_id: str,
    *,
    limit: int = 5,
) -> list[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT bt.*
        FROM banking_transactions bt
        INNER JOIN ledger_entries le ON le.transaction_id = bt.id
        WHERE le.discord_id = ?
        ORDER BY bt.id DESC
        LIMIT ?
        """,
        (discord_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_bank_summary(conn: sqlite3.Connection, discord_id: str) -> Optional[Dict[str, Any]]:
    linked = fetch_linked_account_by_discord_id(conn, discord_id)
    if linked is None:
        return None

    accounts = ensure_member_bank_accounts(
        conn,
        user_id=int(linked["user_id"]),
        discord_id=discord_id,
    )
    checking = accounts.get("checking")
    savings = accounts.get("savings")
    if checking is None or savings is None:
        return None

    recent = list_recent_banking_transactions_for_user(conn, discord_id, limit=5)
    checking_balance = int(checking["balance"])
    savings_balance = int(savings["balance"])
    return {
        "linked_account": linked,
        "checking": checking,
        "savings": savings,
        "checking_balance": checking_balance,
        "savings_balance": savings_balance,
        "total_balance": checking_balance + savings_balance,
        "recent_transactions": recent,
    }


def fetch_banking_transaction_by_idempotency_key(
    conn: sqlite3.Connection,
    idempotency_key: str,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM banking_transactions WHERE idempotency_key = ? LIMIT 1",
        (idempotency_key,),
    ).fetchone()
    return dict(row) if row else None


def transfer_between_members(
    conn: sqlite3.Connection,
    *,
    sender_discord_id: str,
    recipient_discord_id: str,
    amount: int,
    actor_id: str,
    transaction_key: str,
    idempotency_key: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    if amount <= 0:
        raise ValueError("Transfer amount must be positive.")
    if sender_discord_id == recipient_discord_id:
        raise ValueError("Sender and recipient must be different members.")

    sender_linked = fetch_linked_account_by_discord_id(conn, sender_discord_id)
    recipient_linked = fetch_linked_account_by_discord_id(conn, recipient_discord_id)
    if sender_linked is None or recipient_linked is None:
        raise ValueError("Both members must have linked bank profiles.")

    sender_accounts = ensure_member_bank_accounts(
        conn,
        user_id=int(sender_linked["user_id"]),
        discord_id=sender_discord_id,
    )
    recipient_accounts = ensure_member_bank_accounts(
        conn,
        user_id=int(recipient_linked["user_id"]),
        discord_id=recipient_discord_id,
    )
    sender_checking = sender_accounts.get("checking")
    recipient_checking = recipient_accounts.get("checking")
    if sender_checking is None or recipient_checking is None:
        raise ValueError("Victor could not prepare the checking accounts.")

    sender_balance = int(sender_checking["balance"])
    if sender_balance < amount:
        raise ValueError("Insufficient checking funds.")

    transaction_id = create_banking_transaction(
        conn,
        transaction_key=transaction_key,
        transaction_type="INTERNAL_TRANSFER",
        status="COMPLETED",
        amount=amount,
        actor_id=actor_id,
        source_system="DISCORD",
        idempotency_key=idempotency_key,
        reference_type="MEMBER_TRANSFER",
        reference_id=f"{sender_discord_id}:{recipient_discord_id}",
        metadata={
            "sender_discord_id": sender_discord_id,
            "recipient_discord_id": recipient_discord_id,
            "note": note or "",
        },
    )

    new_sender_balance = sender_balance - amount
    new_recipient_balance = int(recipient_checking["balance"]) + amount
    update_bank_account_balance(conn, int(sender_checking["id"]), new_sender_balance)
    update_bank_account_balance(conn, int(recipient_checking["id"]), new_recipient_balance)

    create_ledger_entry(
        conn,
        transaction_id=transaction_id,
        account_id=int(sender_checking["id"]),
        user_id=int(sender_linked["user_id"]),
        discord_id=sender_discord_id,
        entry_kind="DEBIT",
        amount=amount,
        balance_after=new_sender_balance,
        note=note or f"Transfer to {recipient_discord_id}",
    )
    create_ledger_entry(
        conn,
        transaction_id=transaction_id,
        account_id=int(recipient_checking["id"]),
        user_id=int(recipient_linked["user_id"]),
        discord_id=recipient_discord_id,
        entry_kind="CREDIT",
        amount=amount,
        balance_after=new_recipient_balance,
        note=note or f"Transfer from {sender_discord_id}",
    )

    return {
        "transaction_id": transaction_id,
        "sender_linked": sender_linked,
        "recipient_linked": recipient_linked,
        "sender_balance_after": new_sender_balance,
        "recipient_balance_after": new_recipient_balance,
        "amount": amount,
        "note": note or "",
    }


def create_treasury_snapshot(
    conn: sqlite3.Connection,
    *,
    observed_wallet_balance: int,
    ledger_treasury_balance: int,
    total_user_liabilities: int,
    total_savings_liabilities: int,
    total_checking_liabilities: int,
    total_pending_withdrawals: int,
    status: str,
    details: Optional[dict[str, Any]] = None,
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO treasury_snapshots (
          observed_wallet_balance,
          ledger_treasury_balance,
          total_user_liabilities,
          total_savings_liabilities,
          total_checking_liabilities,
          total_pending_withdrawals,
          status,
          details,
          created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observed_wallet_balance,
            ledger_treasury_balance,
            total_user_liabilities,
            total_savings_liabilities,
            total_checking_liabilities,
            total_pending_withdrawals,
            status,
            json.dumps(details or {}),
            now,
        ),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def upsert_project(
    conn: sqlite3.Connection,
    *,
    project_key: str,
    project_name: str,
    created_by: str,
    status: str = "ACTIVE",
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO projects (
          project_key,
          project_name,
          status,
          created_by,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_key) DO UPDATE SET
          project_name = excluded.project_name,
          status = excluded.status,
          updated_at = excluded.updated_at
        """,
        (project_key, project_name, status, created_by, now, now),
    )
    row = conn.execute("SELECT id FROM projects WHERE project_key = ?", (project_key,)).fetchone()
    return int(row["id"])


def create_project_update(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    fold_key: str,
    update_type: str,
    title: str,
    details: str,
    created_by: str,
) -> int:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO project_updates (
          project_id,
          fold_key,
          update_type,
          title,
          details,
          created_by,
          created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, fold_key, update_type, title, details, created_by, now),
    )
    conn.execute(
        "UPDATE projects SET updated_at = ? WHERE id = ?",
        (now, project_id),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    return int(row["id"])


def list_recent_project_updates(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          pu.*,
          p.project_name,
          p.project_key
        FROM project_updates pu
        INNER JOIN projects p ON p.id = pu.project_id
        ORDER BY pu.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_vouch(
    conn: sqlite3.Connection,
    *,
    source_message_id: str,
    guild_id: Optional[str],
    channel_id: str,
    subject_discord_id: str,
    voucher_discord_id: Optional[str],
    details: str,
    source_url: Optional[str],
    created_at: str,
) -> str:
    now = _utc_now()
    existing = conn.execute(
        "SELECT id FROM vouches WHERE source_message_id = ?",
        (source_message_id,),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE vouches
            SET guild_id = ?,
                channel_id = ?,
                subject_discord_id = ?,
                voucher_discord_id = ?,
                details = ?,
                source_url = ?,
                created_at = ?,
                updated_at = ?
            WHERE source_message_id = ?
            """,
            (
                guild_id,
                channel_id,
                subject_discord_id,
                voucher_discord_id,
                details,
                source_url,
                created_at,
                now,
                source_message_id,
            ),
        )
        return "updated"

    conn.execute(
        """
        INSERT INTO vouches (
          source_message_id,
          guild_id,
          channel_id,
          subject_discord_id,
          voucher_discord_id,
          details,
          source_url,
          created_at,
          imported_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_message_id,
            guild_id,
            channel_id,
            subject_discord_id,
            voucher_discord_id,
            details,
            source_url,
            created_at,
            now,
            now,
        ),
    )
    return "inserted"


def count_vouches_for_member(conn: sqlite3.Connection, subject_discord_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM vouches WHERE subject_discord_id = ?",
        (subject_discord_id,),
    ).fetchone()
    return int(row["count"]) if row else 0


def list_vouches_for_member(
    conn: sqlite3.Connection,
    *,
    subject_discord_id: str,
    limit: int = 5,
) -> list[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM vouches
        WHERE subject_discord_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (subject_discord_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]
