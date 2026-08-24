"""Phase 1 tests — intelligence API + regression on the legacy checker bridge.

Run from backend/:  python -m pytest tests/ -q
Uses a throwaway SQLite file; no Postgres or network to registrars required.
"""
import os
import tempfile

# Configure BEFORE importing the app (config/db read env at import time).
_TMP_DB = os.path.join(tempfile.gettempdir(), "allotcheck_test_phase1.db")
for suffix in ("", "-wal", "-shm"):
    try:
        os.remove(_TMP_DB + suffix)
    except OSError:
        pass
os.environ["ALLOTCHECK_DB"] = _TMP_DB
os.environ["ALLOTCHECK_ADMIN_TOKEN"] = "test-token"
os.environ.pop("DATABASE_URL", None)

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import repo, db

db.init_db()  # module-level TestClient does not run lifespan; init explicitly
client = TestClient(app)
AUTH = {"x-admin-token": "test-token"}


def test_health_reports_sqlite():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["db"] == "sqlite"


def test_security_headers_present():
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_dashboard_is_honest_when_empty():
    r = client.get("/api/v1/dashboard").json()
    assert r["counts"]["running"] == 0
    assert r["market_data_available"] is False  # never fabricates market data


def test_admin_requires_token():
    assert client.post("/api/v1/admin/ingest-registrars").status_code == 401
    assert client.post("/api/v1/admin/ipo", json={"name": "X"}).status_code == 401


def test_admin_upsert_then_detail_has_honest_envelopes():
    r = client.post("/api/v1/admin/ipo", json={
        "name": "Demo Test IPO Limited", "board": "sme", "status": "upcoming",
        "price_min": 100, "price_max": 105, "lot_size": 150,
    }, headers=AUTH)
    assert r.status_code == 200
    slug = r.json()["slug"]

    d = client.get(f"/api/v1/ipos/{slug}").json()
    assert d["ipo"]["name"] == "Demo Test IPO Limited"
    assert d["ipo"]["price_min"] == 100
    # No sourced GMP/subscription/listing yet -> available:false, not a number.
    assert d["gmp"]["available"] is False
    assert d["subscription"]["available"] is False
    assert d["listing"]["available"] is False
    assert "not investment advice" in d["gmp_disclaimer"].lower()


def test_ipo_list_filter_and_search():
    # created above with status=upcoming
    up = client.get("/api/v1/ipos?status=upcoming").json()
    assert any(i["slug"] == "demo-test-ipo-limited" for i in up["items"])
    hit = client.get("/api/v1/ipos?q=demo test").json()
    assert hit["count"] >= 1
    miss = client.get("/api/v1/ipos?q=zzz-nonexistent-zzz").json()
    assert miss["count"] == 0


def test_missing_ipo_is_404():
    assert client.get("/api/v1/ipos/no-such-ipo-xyz").status_code == 404


def test_data_quality_lists_official_sources():
    d = client.get("/api/v1/data-quality").json()
    keys = {s["key"] for s in d["sources"]}
    assert {"nse", "bse", "kfintech", "mufg", "manual"}.issubset(keys)


# ---- regression: the existing checker must still work through the bridge ----

def test_legacy_registrars_bridge_unchanged():
    r = client.get("/api/registrars")
    assert r.status_code == 200
    keys = {x["key"] for x in r.json()}
    assert {"kfintech", "mufg"}.issubset(keys)


def test_legacy_track_bridge_ok():
    r = client.post("/api/track", json={"type": "pageview"})
    assert r.status_code == 200 and r.json().get("ok") is True


def test_legacy_check_requires_params():
    # missing clientid/pan -> 400 from the checker core (bridge passes it through)
    r = client.get("/api/kfintech/check")
    assert r.status_code == 400


def test_slugify():
    assert repo.slugify("ACCORD TRANSFORMER & SWITCHGEAR LIMITED") == "accord-transformer-switchgear-limited"
