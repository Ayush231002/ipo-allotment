"""Data layer for the IPO read model.

Postgres (psycopg) when DATABASE_URL is set — the production target on Render.
SQLite (stdlib) file otherwise — so local dev and CI need zero services.

The public helpers (`query`, `execute`, `init_db`) hide the dialect. SQL is
written with `?` placeholders and translated to `%s` for Postgres. Only PUBLIC
IPO data is ever stored here — never a PAN or any personal data.
"""
from __future__ import annotations
import os
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_IS_PG = config.DATABASE_URL.startswith("postgres")
_SQLITE_PATH = os.environ.get(
    "ALLOTCHECK_DB",
    os.path.join(os.path.dirname(__file__), "..", ".data", "allotcheck.db"),
)
_init_lock = threading.Lock()
_initialized = False


def is_enabled() -> bool:
    """A DB is always available (SQLite fallback), but report the backend kind."""
    return True


def backend_kind() -> str:
    return "postgres" if _IS_PG else "sqlite"


def _ph(sql: str) -> str:
    return sql.replace("?", "%s") if _IS_PG else sql


@contextmanager
def _connect():
    if _IS_PG:
        import psycopg  # lazy import; only needed in production
        conn = psycopg.connect(config.DATABASE_URL, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()
    else:
        os.makedirs(os.path.dirname(_SQLITE_PATH), exist_ok=True)
        conn = sqlite3.connect(_SQLITE_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_ph(sql), params)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def execute(sql: str, params: tuple = ()) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_ph(sql), params)


# ------------------------------- schema -------------------------------------

def _schema_statements() -> list[str]:
    pk = "BIGSERIAL PRIMARY KEY" if _IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    return [
        # Source registry — every displayed metric points back to one of these.
        f"""CREATE TABLE IF NOT EXISTS data_sources (
            id {pk},
            key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,              -- official | secondary | manual
            reliability TEXT NOT NULL,       -- high | medium | low
            url TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at {ts}
        )""",
        # IPO identity + verified metadata (no financial estimates here).
        f"""CREATE TABLE IF NOT EXISTS ipo (
            id {pk},
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            registrar_key TEXT DEFAULT '',
            registrar_client_id TEXT DEFAULT '',
            board TEXT DEFAULT 'unknown',    -- mainboard | sme | unknown
            status TEXT DEFAULT 'unclassified', -- upcoming|running|closed|listed|unclassified
            exchange TEXT DEFAULT '',
            sector TEXT DEFAULT '',
            open_date TEXT DEFAULT '',
            close_date TEXT DEFAULT '',
            allotment_date TEXT DEFAULT '',
            listing_date TEXT DEFAULT '',
            price_min REAL,
            price_max REAL,
            lot_size INTEGER,
            issue_size_cr REAL,
            source_id INTEGER,
            created_at {ts},
            updated_at {ts}
        )""",
        f"""CREATE TABLE IF NOT EXISTS ipo_subscription_snapshots (
            id {pk},
            ipo_id INTEGER NOT NULL,
            captured_at {ts},
            source_id INTEGER,
            overall_x REAL, qib_x REAL, nii_x REAL, retail_x REAL,
            employee_x REAL, shareholder_x REAL
        )""",
        f"""CREATE TABLE IF NOT EXISTS ipo_gmp_snapshots (
            id {pk},
            ipo_id INTEGER NOT NULL,
            captured_at {ts},
            source_id INTEGER,
            gmp REAL, gmp_pct REAL, note TEXT DEFAULT ''
        )""",
        f"""CREATE TABLE IF NOT EXISTS ipo_listing_data (
            id {pk},
            ipo_id INTEGER NOT NULL,
            source_id INTEGER,
            captured_at {ts},
            listing_price REAL, day_high REAL, day_low REAL, day_close REAL,
            listing_gain_pct REAL
        )""",
        f"""CREATE TABLE IF NOT EXISTS source_fetch_logs (
            id {pk},
            source_id INTEGER,
            ran_at {ts},
            ok INTEGER DEFAULT 1,
            message TEXT DEFAULT ''
        )""",
        f"""CREATE TABLE IF NOT EXISTS data_validation_issues (
            id {pk},
            ipo_id INTEGER,
            field TEXT DEFAULT '',
            severity TEXT DEFAULT 'info',    -- info | warn | error
            detail TEXT DEFAULT '',
            created_at {ts}
        )""",
        f"""CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id {pk},
            actor TEXT DEFAULT '',
            action TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            created_at {ts}
        )""",
        "CREATE INDEX IF NOT EXISTS idx_ipo_status ON ipo(status)",
        "CREATE INDEX IF NOT EXISTS idx_gmp_ipo ON ipo_gmp_snapshots(ipo_id)",
        "CREATE INDEX IF NOT EXISTS idx_sub_ipo ON ipo_subscription_snapshots(ipo_id)",
    ]


# Factual source registry — provenance metadata, NOT financial data.
_SEED_SOURCES = [
    ("nse", "National Stock Exchange", "official", "high", "https://www.nseindia.com", "IPO bidding & listing data"),
    ("bse", "BSE Limited", "official", "high", "https://www.bseindia.com", "IPO bidding & listing data"),
    ("sebi", "SEBI filings (DRHP/RHP)", "official", "high", "https://www.sebi.gov.in", "Offer documents"),
    ("kfintech", "KFintech registrar", "official", "high", "https://ipostatus.kfintech.com", "Allotment status"),
    ("mufg", "MUFG / Intime registrar", "official", "high", "https://in.mpms.mufg.com", "Allotment status"),
    ("manual", "Admin-entered", "manual", "medium", "", "Manually verified entry with attribution"),
]


def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        for stmt in _schema_statements():
            execute(stmt)
        for key, name, typ, rel, url, notes in _SEED_SOURCES:
            existing = query("SELECT id FROM data_sources WHERE key=?", (key,))
            if not existing:
                execute(
                    "INSERT INTO data_sources (key,name,type,reliability,url,notes) VALUES (?,?,?,?,?,?)",
                    (key, name, typ, rel, url, notes),
                )
        _initialized = True


def source_id(key: str) -> int | None:
    r = query("SELECT id FROM data_sources WHERE key=?", (key,))
    return r[0]["id"] if r else None
