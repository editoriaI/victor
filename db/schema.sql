-- Victor bot schema

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  discord_id TEXT UNIQUE NOT NULL,
  highrise_user_id TEXT,
  highrise_username TEXT,
  linked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blacklist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  discord_id TEXT UNIQUE NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  verifier_id TEXT NOT NULL,
  bio_text TEXT,
  result TEXT NOT NULL,
  missing_tags TEXT,
  missing_regex TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS verification_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,
  highrise_user_id TEXT,
  highrise_username TEXT NOT NULL,
  code TEXT NOT NULL,
  status TEXT NOT NULL,
  fail_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  verified_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id TEXT NOT NULL,
  item_name TEXT NOT NULL,
  price INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  buyer_id TEXT NOT NULL,
  item_name TEXT NOT NULL,
  max_price INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id INTEGER NOT NULL,
  seller_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(request_id) REFERENCES match_requests(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  target_id TEXT,
  details TEXT,
  created_at TEXT NOT NULL
);

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
);

CREATE TABLE IF NOT EXISTS command_watch (
  channel_id INTEGER PRIMARY KEY,
  last_message_id INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS feature_flags (
  name TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

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
);

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
);

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
);

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
);

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
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_key TEXT NOT NULL UNIQUE,
  project_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

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
);

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
);

CREATE INDEX IF NOT EXISTS idx_linked_accounts_discord_id ON linked_accounts(discord_id);
CREATE INDEX IF NOT EXISTS idx_bank_accounts_user_type ON bank_accounts(user_id, account_type);
CREATE INDEX IF NOT EXISTS idx_banking_transactions_actor_id ON banking_transactions(actor_id);
CREATE INDEX IF NOT EXISTS idx_banking_transactions_reference ON banking_transactions(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_transaction_id ON ledger_entries(transaction_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_account_id ON ledger_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_project_updates_project_id ON project_updates(project_id);
CREATE INDEX IF NOT EXISTS idx_vouches_subject_discord_id ON vouches(subject_discord_id);
