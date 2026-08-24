"""Phase 2 tests — classification, validation, subscription, dashboard events.

Run from backend/:  python -m pytest tests/ -q
Self-contained SQLite; no Postgres/network. When run alongside test_phase1 they
share one DB (app is imported once) and use unique IPO names to stay independent.
"""
import os
import tempfile
from datetime import date, timedelta

_TMP_DB = os.path.join(tempfile.gettempdir(), "allotcheck_test_phase2.db")
for sfx in ("", "-wal", "-shm"):
    try:
        os.remove(_TMP_DB + sfx)
    except OSError:
        pass
os.environ.setdefault("ALLOTCHECK_DB", _TMP_DB)
os.environ["ALLOTCHECK_ADMIN_TOKEN"] = "test-token"
os.environ.pop("DATABASE_URL", None)
os.environ["SCHEDULER_ENABLED"] = "false"   # no background thread in tests

from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.services import classify

db.init_db()
client = TestClient(app)
AUTH = {"x-admin-token": "test-token"}

TODAY = date.today()
def _iso(delta): return (TODAY + timedelta(days=delta)).isoformat()
YESTERDAY, TOMORROW, TODAY_S = _iso(-1), _iso(1), _iso(0)


# ---------------- pure classification ----------------

def test_classify_upcoming():
    assert classify.status_from_dates(TOMORROW, _iso(3), "", "", TODAY_S) == "upcoming"

def test_classify_running():
    assert classify.status_from_dates(YESTERDAY, TOMORROW, "", "", TODAY_S) == "running"

def test_classify_closed():
    assert classify.status_from_dates(_iso(-7), YESTERDAY, "", "", TODAY_S) == "closed"

def test_classify_listed():
    assert classify.status_from_dates(_iso(-10), _iso(-8), _iso(-6), YESTERDAY, TODAY_S) == "listed"

def test_classify_unclassified_without_dates():
    assert classify.status_from_dates("", "", "", "", TODAY_S) == "unclassified"


# ---------------- admin upsert derives status + validation ----------------

def test_upsert_dated_ipo_is_classified_running():
    r = client.post("/api/v1/admin/ipo", json={
        "name": "Running Demo Ltd", "open_date": YESTERDAY, "close_date": TOMORROW,
        "price_min": 100, "price_max": 110, "lot_size": 100}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["status"] == "running"
    d = client.get("/api/v1/dashboard").json()
    assert d["counts"]["running"] >= 1
    assert d["market_data_available"] is True

def test_validation_blocks_price_inversion():
    r = client.post("/api/v1/admin/ipo", json={
        "name": "Bad Price Ltd", "price_min": 200, "price_max": 100}, headers=AUTH)
    assert r.status_code == 422
    assert "issues" in r.json()["detail"]

def test_validation_blocks_bad_date_format():
    r = client.post("/api/v1/admin/ipo", json={
        "name": "Bad Date Ltd", "open_date": "2026/01/01"}, headers=AUTH)
    assert r.status_code == 422


# ---------------- subscription entry ----------------

def test_subscription_add_and_detail():
    client.post("/api/v1/admin/ipo", json={"name": "Sub Demo Ltd"}, headers=AUTH)
    r = client.post("/api/v1/admin/ipo/sub-demo-ltd/subscription",
                    json={"overall_x": 10.5, "qib_x": 20, "retail_x": 5, "source": "nse"},
                    headers=AUTH)
    assert r.status_code == 200
    d = client.get("/api/v1/ipos/sub-demo-ltd").json()
    assert d["subscription"]["available"] is True
    assert d["subscription"]["value"]["overall_x"] == 10.5
    assert d["subscription"]["source"]  # provenance present

def test_subscription_requires_a_figure():
    client.post("/api/v1/admin/ipo", json={"name": "Empty Sub Ltd"}, headers=AUTH)
    r = client.post("/api/v1/admin/ipo/empty-sub-ltd/subscription", json={}, headers=AUTH)
    assert r.status_code == 422

def test_subscription_requires_admin():
    assert client.post("/api/v1/admin/ipo/sub-demo-ltd/subscription",
                       json={"overall_x": 1}).status_code == 401


# ---------------- dashboard events + reclassify + fetchers ----------------

def test_dashboard_closing_today():
    client.post("/api/v1/admin/ipo", json={
        "name": "Closing Today Ltd", "open_date": YESTERDAY, "close_date": TODAY_S},
        headers=AUTH)
    d = client.get("/api/v1/dashboard").json()
    assert d["today"]["closing_today"] >= 1

def test_reclassify_endpoint():
    r = client.post("/api/v1/admin/reclassify", headers=AUTH).json()
    assert "changed" in r and "counts" in r

def test_official_fetchers_disabled_by_default():
    d = client.get("/api/v1/data-quality").json()
    assert d["fetchers"]["official_fetchers_enabled"] is False
    assert d["fetchers"]["active_data_path"] == "official + admin-entered"
