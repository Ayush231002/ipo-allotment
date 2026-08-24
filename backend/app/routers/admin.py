"""Admin data-operations (token-protected, header-only, constant-time).

Phase 1 ships the ingest that seeds IPO *identity* rows from the registrar
company lists (names + client ids only — never financial estimates), plus a
manual verified-metadata upsert for the "official + admin-entered" data model.
"""
from __future__ import annotations
import hmac
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .. import config, db, repo

router = APIRouter()


def _require_admin(x_admin_token: str | None):
    if not config.ADMIN_ENABLED:
        raise HTTPException(status_code=503, detail="admin disabled: set ALLOTCHECK_ADMIN_TOKEN")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/admin/ingest-registrars")
def ingest_registrars(x_admin_token: str | None = Header(default=None)):
    """Pull each registrar's live company list into IPO identity rows.

    Only names + registrar client ids are stored. No GMP, subscription, price
    or listing data is invented here.
    """
    _require_admin(x_admin_token)
    import registrars as reg  # backend/ on path via legacy setup

    added, seen, errors = 0, 0, {}
    for meta in reg.list_registrars():
        key = meta["key"]
        try:
            for c in reg.get(key).list_companies():
                name = (c.get("name") or "").strip()
                if not name:
                    continue
                before = repo.get_ipo(repo.slugify(name))
                repo.upsert_ipo_identity(name, key, str(c.get("id") or ""))
                seen += 1
                if not before:
                    added += 1
        except Exception as e:  # a registrar being busy must not fail the whole run
            errors[key] = str(e)[:120]

    db.execute("INSERT INTO source_fetch_logs (source_id, ok, message) VALUES (?,?,?)",
               (db.source_id("manual"), 1 if not errors else 0,
                f"ingest: +{added} new, {seen} seen, errors={list(errors)}"))
    repo.audit("admin", "ingest-registrars", f"+{added}/{seen}")
    return {"ok": True, "added": added, "seen": seen, "errors": errors,
            "total_indexed": repo.count_ipos()}


class IpoUpsert(BaseModel):
    name: str
    board: str | None = None
    status: str | None = None
    exchange: str | None = None
    sector: str | None = None
    open_date: str | None = None
    close_date: str | None = None
    allotment_date: str | None = None
    listing_date: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    lot_size: int | None = None
    issue_size_cr: float | None = None


@router.post("/admin/ipo")
def upsert_ipo(payload: IpoUpsert, x_admin_token: str | None = Header(default=None)):
    """Create/update verified IPO metadata (the admin-entered data path)."""
    _require_admin(x_admin_token)
    slug = repo.slugify(payload.name)
    existing = repo.get_ipo(slug)
    fields = payload.model_dump(exclude_none=True)
    src = db.source_id("manual")

    if existing:
        sets, params = [], []
        for k, v in fields.items():
            if k == "name":
                continue
            sets.append(f"{k}=?"); params.append(v)
        sets.append("source_id=?"); params.append(src)
        sets.append("updated_at=CURRENT_TIMESTAMP")
        params.append(slug)
        db.execute(f"UPDATE ipo SET {', '.join(sets)} WHERE slug=?", tuple(params))
        action = "update"
    else:
        cols = ["slug", "name", "source_id"] + [k for k in fields if k != "name"]
        vals = [slug, payload.name, src] + [fields[k] for k in fields if k != "name"]
        ph = ",".join(["?"] * len(cols))
        db.execute(f"INSERT INTO ipo ({','.join(cols)}) VALUES ({ph})", tuple(vals))
        action = "create"

    repo.audit("admin", f"ipo-{action}", slug)
    return {"ok": True, "slug": slug, "action": action}
