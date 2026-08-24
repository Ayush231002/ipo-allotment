"""IPO read-model access. Keeps SQL out of the routers.

Every read that surfaces a financial metric also returns its freshness
(source + captured_at) so the UI can label provenance and never present stale
or unsourced numbers as live. Missing data returns None/empty — never a
fabricated value.
"""
from __future__ import annotations
import re
import time

from . import db


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "ipo"


# ------------------------------- IPOs ---------------------------------------

def list_ipos(status: str = "", board: str = "", q: str = "",
              limit: int = 50, offset: int = 0) -> list[dict]:
    where, params = [], []
    if status:
        where.append("status = ?"); params.append(status)
    if board:
        where.append("board = ?"); params.append(board)
    if q:
        where.append("LOWER(name) LIKE ?"); params.append("%" + q.lower() + "%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    rows = db.query(
        f"SELECT id,slug,name,registrar_key,board,status,exchange,sector,"
        f"open_date,close_date,allotment_date,listing_date,price_min,price_max,"
        f"lot_size,issue_size_cr,updated_at FROM ipo {clause} "
        f"ORDER BY name ASC LIMIT ? OFFSET ?",
        tuple(params) + (limit, offset),
    )
    return rows


def count_ipos(status: str = "") -> int:
    if status:
        r = db.query("SELECT COUNT(*) AS n FROM ipo WHERE status=?", (status,))
    else:
        r = db.query("SELECT COUNT(*) AS n FROM ipo")
    return int(r[0]["n"]) if r else 0


def get_ipo(slug: str) -> dict | None:
    r = db.query("SELECT * FROM ipo WHERE slug=?", (slug,))
    return r[0] if r else None


def latest_gmp(ipo_id: int) -> dict | None:
    r = db.query(
        "SELECT g.gmp,g.gmp_pct,g.note,g.captured_at,s.name AS source,s.type AS source_type "
        "FROM ipo_gmp_snapshots g LEFT JOIN data_sources s ON s.id=g.source_id "
        "WHERE g.ipo_id=? ORDER BY g.captured_at DESC LIMIT 1", (ipo_id,))
    return r[0] if r else None


def gmp_history(ipo_id: int, limit: int = 60) -> list[dict]:
    return db.query(
        "SELECT gmp,gmp_pct,note,captured_at FROM ipo_gmp_snapshots "
        "WHERE ipo_id=? ORDER BY captured_at ASC LIMIT ?", (ipo_id, limit))


def latest_subscription(ipo_id: int) -> dict | None:
    r = db.query(
        "SELECT sub.*, s.name AS source, s.type AS source_type "
        "FROM ipo_subscription_snapshots sub LEFT JOIN data_sources s ON s.id=sub.source_id "
        "WHERE sub.ipo_id=? ORDER BY sub.captured_at DESC LIMIT 1", (ipo_id,))
    return r[0] if r else None


def listing(ipo_id: int) -> dict | None:
    r = db.query(
        "SELECT l.*, s.name AS source FROM ipo_listing_data l "
        "LEFT JOIN data_sources s ON s.id=l.source_id "
        "WHERE l.ipo_id=? ORDER BY l.captured_at DESC LIMIT 1", (ipo_id,))
    return r[0] if r else None


def upsert_ipo_identity(name: str, registrar_key: str, client_id: str) -> str:
    """Insert an IPO identity row from a registrar company list (name + id only —
    NO financial data). Returns the slug. Idempotent on slug."""
    slug = slugify(name)
    existing = get_ipo(slug)
    if existing:
        db.execute(
            "UPDATE ipo SET registrar_key=?, registrar_client_id=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE slug=?", (registrar_key, client_id, slug))
        return slug
    src = db.source_id(registrar_key) or db.source_id("manual")
    db.execute(
        "INSERT INTO ipo (slug,name,registrar_key,registrar_client_id,source_id) "
        "VALUES (?,?,?,?,?)", (slug, name.strip(), registrar_key, client_id, src))
    return slug


# ------------------------------- sources / quality --------------------------

def sources() -> list[dict]:
    return db.query("SELECT key,name,type,reliability,url,notes FROM data_sources ORDER BY type,name")


def recent_fetch_logs(limit: int = 20) -> list[dict]:
    return db.query(
        "SELECT l.ran_at,l.ok,l.message,s.name AS source FROM source_fetch_logs l "
        "LEFT JOIN data_sources s ON s.id=l.source_id ORDER BY l.ran_at DESC LIMIT ?",
        (limit,))


def validation_issue_counts() -> dict:
    rows = db.query("SELECT severity, COUNT(*) AS n FROM data_validation_issues GROUP BY severity")
    out = {"info": 0, "warn": 0, "error": 0}
    for r in rows:
        out[r["severity"]] = int(r["n"])
    return out


def audit(actor: str, action: str, detail: str = "") -> None:
    db.execute("INSERT INTO admin_audit_logs (actor,action,detail) VALUES (?,?,?)",
               (actor, action, detail))
