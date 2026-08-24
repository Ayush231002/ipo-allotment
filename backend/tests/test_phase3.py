"""Phase 3 tests — GMP snapshots, trend analytics, dashboard summary, disclaimer."""
import os
import tempfile

_TMP_DB = os.path.join(tempfile.gettempdir(), "allotcheck_test_phase3.db")
for sfx in ("", "-wal", "-shm"):
    try:
        os.remove(_TMP_DB + sfx)
    except OSError:
        pass
os.environ.setdefault("ALLOTCHECK_DB", _TMP_DB)
os.environ["ALLOTCHECK_ADMIN_TOKEN"] = "test-token"
os.environ.pop("DATABASE_URL", None)
os.environ["SCHEDULER_ENABLED"] = "false"

from fastapi.testclient import TestClient
from app.main import app
from app import db

db.init_db()
client = TestClient(app)
AUTH = {"x-admin-token": "test-token"}


def _mk(name):
    client.post("/api/v1/admin/ipo", json={"name": name}, headers=AUTH)
    return name.lower().replace(" ", "-")


def test_gmp_requires_admin():
    slug = _mk("Gmp Auth Ltd")
    assert client.post(f"/api/v1/admin/ipo/{slug}/gmp", json={"gmp": 10}).status_code == 401


def test_gmp_missing_value_is_422():
    slug = _mk("Gmp Empty Ltd")
    assert client.post(f"/api/v1/admin/ipo/{slug}/gmp", json={"note": "x"}, headers=AUTH).status_code == 422


def test_gmp_add_and_trend_analytics():
    slug = _mk("Gmp Trend Ltd")
    for v, p in [(50, 12.5), (60, 15.0), (55, 13.7)]:
        r = client.post(f"/api/v1/admin/ipo/{slug}/gmp",
                        json={"gmp": v, "gmp_pct": p, "source": "manual"}, headers=AUTH)
        assert r.status_code == 200
    a = client.get(f"/api/v1/ipos/{slug}/gmp").json()["analytics"]
    assert a["available"] is True
    assert a["count"] == 3
    assert a["current"] == 55        # last inserted (id tiebreaker keeps order)
    assert a["previous"] == 60
    assert a["change"] == -5
    assert a["high"] == 60 and a["low"] == 50
    assert a["volatility"] > 0
    assert len(a["history"]) == 3


def test_gmp_negative_premium_allowed():
    slug = _mk("Gmp Discount Ltd")
    r = client.post(f"/api/v1/admin/ipo/{slug}/gmp", json={"gmp": -8}, headers=AUTH)
    assert r.status_code == 200
    a = client.get(f"/api/v1/ipos/{slug}/gmp").json()["analytics"]
    assert a["current"] == -8


def test_gmp_disclaimer_present():
    slug = _mk("Gmp Disc Ltd")
    d = client.get(f"/api/v1/ipos/{slug}/gmp").json()
    assert "not investment advice" in d["disclaimer"].lower()


def test_dashboard_gmp_summary():
    slug = _mk("Gmp Top Ltd")
    client.post(f"/api/v1/admin/ipo/{slug}/gmp", json={"gmp": 999}, headers=AUTH)
    g = client.get("/api/v1/dashboard").json()["gmp"]
    assert g["active_count"] >= 1
    assert g["highest"] is not None
    assert g["highest"]["gmp"] == 999   # highest across all indexed IPOs


def test_detail_gmp_envelope_still_latest():
    slug = _mk("Gmp Latest Ltd")
    client.post(f"/api/v1/admin/ipo/{slug}/gmp", json={"gmp": 20, "gmp_pct": 5}, headers=AUTH)
    d = client.get(f"/api/v1/ipos/{slug}").json()
    assert d["gmp"]["available"] is True
    assert d["gmp"]["value"]["gmp"] == 20
