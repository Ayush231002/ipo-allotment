"""IPO read model: dashboard overview, directory list, and detail pages.

Honest-by-construction: financial sections return `available: false` with a
reason when there is no sourced data yet, so the UI shows "Awaiting data"
instead of a fabricated number.
"""
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, HTTPException, Query

from .. import repo

router = APIRouter()

DISCLAIMER_GMP = ("GMP is unofficial, varies by source, and does not guarantee "
                  "the listing price. This is not investment advice.")


def _metric(available: bool, value=None, source: str = "", captured_at: str = "",
            reason: str = ""):
    """Uniform provenance envelope for every financial metric."""
    return {"available": available, "value": value, "source": source,
            "captured_at": captured_at, "reason": reason}


@router.get("/dashboard")
def dashboard():
    """Overview counters — computed from the read model, real zeros when empty."""
    counts = {
        "running": repo.count_ipos("running"),
        "upcoming": repo.count_ipos("upcoming"),
        "closed": repo.count_ipos("closed"),
        "listed": repo.count_ipos("listed"),
        "indexed_total": repo.count_ipos(),
    }
    return {
        "as_of": date.today().isoformat(),
        "counts": counts,
        "market_data_available": counts["running"] + counts["upcoming"] > 0,
        "note": "Market metadata (dates, subscription, GMP, listing) is populated "
                "by the data pipeline in Phase 2. Identity records may already be "
                "present from registrar lists.",
    }


@router.get("/ipos")
def list_ipos(status: str = "", board: str = "", q: str = "",
              limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    items = repo.list_ipos(status=status, board=board, q=q, limit=limit, offset=offset)
    return {
        "items": items,
        "count": len(items),
        "filters": {"status": status, "board": board, "q": q},
        "offset": offset,
        "limit": limit,
    }


@router.get("/ipos/{slug}")
def ipo_detail(slug: str):
    ipo = repo.get_ipo(slug)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found")

    ipo_id = ipo["id"]

    gmp = repo.latest_gmp(ipo_id)
    sub = repo.latest_subscription(ipo_id)
    lst = repo.listing(ipo_id)

    return {
        "ipo": {
            "slug": ipo["slug"], "name": ipo["name"], "board": ipo["board"],
            "status": ipo["status"], "exchange": ipo["exchange"], "sector": ipo["sector"],
            "registrar_key": ipo["registrar_key"],
            "registrar_client_id": ipo["registrar_client_id"],
            "open_date": ipo["open_date"], "close_date": ipo["close_date"],
            "allotment_date": ipo["allotment_date"], "listing_date": ipo["listing_date"],
            "price_min": ipo["price_min"], "price_max": ipo["price_max"],
            "lot_size": ipo["lot_size"], "issue_size_cr": ipo["issue_size_cr"],
            "updated_at": ipo["updated_at"],
        },
        "gmp": _metric(
            bool(gmp), gmp and {"gmp": gmp["gmp"], "gmp_pct": gmp["gmp_pct"], "note": gmp["note"]},
            gmp["source"] if gmp else "", gmp["captured_at"] if gmp else "",
            "" if gmp else "No GMP data from configured sources yet.",
        ),
        "gmp_disclaimer": DISCLAIMER_GMP,
        "subscription": _metric(
            bool(sub),
            sub and {k: sub[k] for k in ("overall_x", "qib_x", "nii_x", "retail_x",
                                         "employee_x", "shareholder_x")},
            sub["source"] if sub else "", sub["captured_at"] if sub else "",
            "" if sub else "No subscription data available yet.",
        ),
        "listing": _metric(
            bool(lst),
            lst and {k: lst[k] for k in ("listing_price", "day_high", "day_low",
                                         "day_close", "listing_gain_pct")},
            lst["source"] if lst else "", lst["captured_at"] if lst else "",
            "" if lst else "Not listed yet, or listing data not available.",
        ),
        # Phase 5 will fill this with a transparent, weighted estimate range.
        "listing_estimate": _metric(False, reason="Estimation engine arrives in Phase 5."),
    }


@router.get("/ipos/{slug}/gmp")
def ipo_gmp(slug: str):
    ipo = repo.get_ipo(slug)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found")
    history = repo.gmp_history(ipo["id"])
    return {"slug": slug, "history": history, "count": len(history),
            "disclaimer": DISCLAIMER_GMP}
