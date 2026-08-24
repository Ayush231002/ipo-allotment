"""Official data-source fetcher framework (scaffolding).

DECISION (locked): data is **official + admin-entered only**. Auto-fetchers for
NSE/BSE are defined here as a pluggable interface but ship DISABLED
(config.ENABLE_OFFICIAL_FETCHERS, default False) and unimplemented, so the
platform never scrapes a source in violation of its terms, robots rules, auth
or rate limits. The compliant, working data path in Phase 2 is admin entry
(POST /api/v1/admin/ipo + /subscription), which records source='manual'.

To add a real official fetcher later:
  1. Subclass Fetcher, implement fetch() against an OFFICIAL, permitted API.
  2. Confirm the source's ToS/robots/rate-limits allow programmatic access.
  3. Register it in REGISTRY and flip ENABLE_OFFICIAL_FETCHERS on.
Each run must write a source_fetch_logs row and pass data through
services.validate before persisting.
"""
from __future__ import annotations

from .. import config


class Fetcher:
    source_key: str = ""       # must match a data_sources.key
    label: str = ""

    def available(self) -> bool:
        """Only run when explicitly enabled AND actually implemented."""
        return False

    def fetch(self) -> list[dict]:
        raise NotImplementedError(
            "No compliant official fetcher is implemented yet. Use admin entry.")


# Registry of known (not-yet-enabled) official fetchers.
REGISTRY: dict[str, Fetcher] = {}


def enabled_fetchers() -> list[Fetcher]:
    if not config.ENABLE_OFFICIAL_FETCHERS:
        return []
    return [f for f in REGISTRY.values() if f.available()]


def status() -> dict:
    """Reported by /api/v1/data-quality so the UI can show sourcing posture."""
    return {
        "official_fetchers_enabled": config.ENABLE_OFFICIAL_FETCHERS,
        "registered": [{"key": f.source_key, "label": f.label, "available": f.available()}
                       for f in REGISTRY.values()],
        "active_data_path": "official + admin-entered",
    }
