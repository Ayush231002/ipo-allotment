"""Meta endpoints: health, registrar list, data-quality/source registry."""
from __future__ import annotations
from fastapi import APIRouter

from .. import db, repo, legacy, sources

router = APIRouter()


@router.get("/health")
def health():
    return {
        "ok": True,
        "service": "allotcheck-intelligence",
        "phase": 1,
        "db": db.backend_kind(),
        "ipos_indexed": repo.count_ipos(),
    }


@router.get("/registrars")
def registrars():
    # Delegate to the checker's own registry so the switcher stays in sync.
    import registrars as reg  # from backend/ via legacy path setup
    return reg.list_registrars()


@router.get("/data-quality")
def data_quality():
    """Real source status, not hard-coded. Drives the data-quality indicator."""
    return {
        "sources": repo.sources(),
        "recent_fetches": repo.recent_fetch_logs(),
        "validation_issues": repo.validation_issue_counts(),
        "fetchers": sources.status(),
        "note": "Financial metrics are shown only with a source and timestamp. "
                "Unavailable data is labelled, never fabricated.",
    }
