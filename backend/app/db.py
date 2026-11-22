"""SQLite access. Tables in Annex C are created exactly as specified (extra columns are
allowed by the guide and only ever added, never renamed). A new connection is opened per
unit of work, so FastAPI worker threads never share one."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS schemes (
    scheme_id TEXT PRIMARY KEY, name_en TEXT, name_hi TEXT, name_kn TEXT, name_ta TEXT,
    department TEXT, benefit_type TEXT, benefit_summary TEXT, status TEXT,
    apply_from TEXT, apply_until TEXT, source_id TEXT,
    benefit_summary_hi TEXT, benefit_summary_kn TEXT, benefit_summary_ta TEXT
);
CREATE TABLE IF NOT EXISTS eligibility_rules (
    rule_id TEXT PRIMARY KEY, scheme_id TEXT REFERENCES schemes(scheme_id), attribute TEXT,
    operator TEXT, value TEXT, rule_group TEXT, effective_from TEXT, valid_until TEXT,
    source_id TEXT, source_section TEXT,
    loaded_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS required_documents (
    scheme_id TEXT, document_name TEXT, mandatory TEXT, notes TEXT,
    document_name_hi TEXT, document_name_kn TEXT, document_name_ta TEXT,
    PRIMARY KEY (scheme_id, document_name)
);
CREATE TABLE IF NOT EXISTS service_centres (
    centre_id TEXT PRIMARY KEY, name TEXT, district TEXT, block TEXT, address TEXT,
    working_days TEXT, working_hours TEXT, languages TEXT, contact_phone TEXT
);
CREATE TABLE IF NOT EXISTS citizens (
    citizen_id TEXT PRIMARY KEY, full_name TEXT, phone TEXT, date_of_birth TEXT, gender TEXT,
    district TEXT, residence_type TEXT, annual_household_income INTEGER, occupation TEXT,
    category TEXT, is_disabled TEXT, disability_percent INTEGER, land_holding_acres REAL,
    preferred_language TEXT, consent_given TEXT, national_id_last4 TEXT, edge_case_note TEXT
);
CREATE TABLE IF NOT EXISTS applications (
    application_id TEXT PRIMARY KEY, citizen_id TEXT, scheme_id TEXT, status TEXT,
    status_updated_on TEXT, remarks TEXT, payload_json TEXT
);
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id TEXT PRIMARY KEY, citizen_id TEXT, centre_id TEXT, slot_start TEXT,
    status TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS reminders (
    reminder_id TEXT PRIMARY KEY, citizen_id TEXT, remind_at TEXT, text TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY, conversation_id TEXT, citizen_id TEXT, action_type TEXT,
    payload_json TEXT, status TEXT, created_at TEXT, expires_at TEXT,
    result_json TEXT, executed_at TEXT, language TEXT
);
CREATE TABLE IF NOT EXISTS policy_registry (
    rule_id TEXT PRIMARY KEY, description TEXT, parameter TEXT, operator TEXT, value TEXT,
    scope_schemes TEXT, effective_from TEXT, source_id TEXT, source_section TEXT
);
CREATE TABLE IF NOT EXISTS referrals (
    referral_id TEXT PRIMARY KEY, conversation_id TEXT, citizen_id TEXT, queue TEXT,
    priority TEXT, created_at TEXT, bundle_json TEXT
);
-- ---- additional tables (allowed by the guide) ----
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY, doc_type TEXT, title TEXT, language TEXT,
    authority_level INTEGER, scheme_id TEXT, last_updated TEXT, effective_from TEXT,
    valid_until TEXT, supersedes TEXT, provenance TEXT, synthetic TEXT, file TEXT,
    content TEXT, contains_instructions TEXT DEFAULT 'N', ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS doc_effects (
    effect_id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, scheme_id TEXT,
    effect_type TEXT, field TEXT, new_value TEXT, values_json TEXT,
    effective_from TEXT, last_updated TEXT, authority_level INTEGER
);
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY, citizen_id TEXT, created_at TEXT, updated_at TEXT,
    state_json TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT, role TEXT, text TEXT,
    trace_id TEXT, answer_type TEXT, route_json TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS audit (
    trace_id TEXT PRIMARY KEY, conversation_id TEXT, created_at TEXT, record_json TEXT
);
CREATE TABLE IF NOT EXISTS id_counters (name TEXT PRIMARY KEY, value INTEGER);
CREATE TABLE IF NOT EXISTS auth_accounts (
    username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'admin')),
    citizen_id TEXT UNIQUE REFERENCES citizens(citizen_id),
    CHECK ((role = 'user' AND citizen_id IS NOT NULL) OR (role = 'admin' AND citizen_id IS NULL))
);
CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY, username TEXT REFERENCES auth_accounts(username),
    guest_id TEXT, expires_at INTEGER NOT NULL,
    CHECK ((username IS NULL) != (guest_id IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at);
CREATE TABLE IF NOT EXISTS auth_login_attempts (
    username TEXT NOT NULL, client_ip TEXT NOT NULL, expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL,
    PRIMARY KEY (username, client_ip)
);
CREATE INDEX IF NOT EXISTS idx_auth_attempts_expiry ON auth_login_attempts(expires_at);
CREATE INDEX IF NOT EXISTS idx_rules_scheme ON eligibility_rules(scheme_id);
CREATE INDEX IF NOT EXISTS idx_effects_scheme ON doc_effects(scheme_id);
CREATE INDEX IF NOT EXISTS idx_msgs_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations(citizen_id, updated_at);
"""

_init_lock = threading.Lock()
_initialised = False


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")  # judges may load rules before schemes
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    global _initialised
    with _init_lock:
        conn = connect()
        try:
            conn.executescript(SCHEMA)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(citizens)").fetchall()}
            for col in ("national_id_last4", "edge_case_note"):
                if col not in cols:
                    conn.execute(f"ALTER TABLE citizens ADD COLUMN {col} TEXT")
            conn.commit()
        finally:
            conn.close()
        _initialised = True


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    if not _initialised:
        init_db()
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(conn: sqlite3.Connection, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def row(conn: sqlite3.Connection, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def next_id(conn: sqlite3.Connection, name: str, prefix: str, width: int = 4, start: int = 1) -> str:
    """Monotonic human-readable IDs such as ACT-0058 or RF-0042."""
    value = conn.execute("""INSERT INTO id_counters(name, value) VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET value=value+1 RETURNING value""", (name, start)).fetchone()["value"]
    return f"{prefix}{value:0{width}d}"


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
