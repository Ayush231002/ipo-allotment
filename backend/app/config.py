"""Runtime configuration, read from environment only (never hard-coded)."""
from __future__ import annotations
import os

# Postgres in production (Render), SQLite file for local dev when unset.
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()

# Admin token gates data-operations endpoints. Same rules as the checker core:
# the literal "changeme" or an empty value means "admin disabled".
ADMIN_TOKEN = (os.environ.get("ALLOTCHECK_ADMIN_TOKEN") or "").strip()
ADMIN_ENABLED = bool(ADMIN_TOKEN) and ADMIN_TOKEN != "changeme"

def _flag(name: str, default: bool) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


# --- Phase 2: scheduler + data sourcing ---
# The classifier is internal (no external calls), so it runs by default.
SCHEDULER_ENABLED = _flag("SCHEDULER_ENABLED", True)
CLASSIFY_INTERVAL_SECONDS = int(os.environ.get("CLASSIFY_INTERVAL_SECONDS") or 900)
# Official auto-fetchers (NSE/BSE) are OFF by default — they must never run
# without an explicit opt-in and a ToS/robots-compliant implementation.
ENABLE_OFFICIAL_FETCHERS = _flag("ENABLE_OFFICIAL_FETCHERS", False)

# Where the SPA lives (…/web).
import os.path as _p
WEB_DIR = _p.normpath(_p.join(_p.dirname(__file__), "..", "..", "web"))

# Content-Security-Policy for HTML docs. connect-src MUST allow KFintech's
# CORS-open check API (called directly from the browser) or the direct path
# breaks; MUFG is proxied so 'self' covers it.
CSP = ("default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
       "object-src 'none'; form-action 'self'; img-src 'self' data:; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; script-src 'self'; "
       "connect-src 'self' https://*.execute-api.ap-south-1.amazonaws.com")
