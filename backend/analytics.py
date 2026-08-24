"""
Lightweight, privacy-first analytics for AllotCheck.

WHAT IT STORES: only anonymous aggregate counters (page views, unique visits,
checks run, per-registrar result tallies, country, device, top IPOs).
WHAT IT NEVER STORES: PANs, names, or any personal data.

Local dev uses a JSON file (this module). On AWS Lambda the filesystem is
ephemeral, so swap `_load`/`_save` for a DynamoDB-backed store at deploy time
(see docs/ARCHITECTURE.md → Analytics). The public API of this module stays the
same, so nothing else changes.
"""
from __future__ import annotations
import json
import os
import threading
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), ".data")
DATA_FILE = os.path.join(DATA_DIR, "analytics.json")
_lock = threading.Lock()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _empty():
    return {"days": {}, "totals": {"pageviews": 0, "visits": 0, "checks": 0, "pans": 0}}


def _load():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _empty()


def _save(d):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, DATA_FILE)


def _day(store, day):
    return store["days"].setdefault(day, {
        "pageviews": 0, "visits": 0, "checks": 0, "pans": 0,
        "reg": {}, "country": {}, "device": {}, "ipos": {},
    })


def track(event: dict, country: str = "??", device: str = "desktop"):
    """Record one anonymous event. Never receives or stores a PAN."""
    if not isinstance(event, dict):
        return
    et = event.get("type")
    with _lock:
        s = _load()
        d = _day(s, _today())
        t = s["totals"]
        if et == "pageview":
            d["pageviews"] += 1; t["pageviews"] += 1
        elif et == "visit":
            d["visits"] += 1; t["visits"] += 1
            country = (country or "??")[:2].upper()
            d["country"][country] = d["country"].get(country, 0) + 1
            device = device if device in ("mobile", "desktop", "tablet") else "desktop"
            d["device"][device] = d["device"].get(device, 0) + 1
        elif et == "check_run":
            reg = str(event.get("registrar", "?"))[:20]
            n = int(event.get("count", 0) or 0)
            d["checks"] += 1; t["checks"] += 1
            d["pans"] += n; t["pans"] += n
            r = d["reg"].setdefault(reg, {"checks": 0, "ok": 0, "no": 0, "busy": 0, "err": 0})
            r["checks"] += 1
            res = event.get("results") or {}
            for k in ("ok", "no", "busy", "err"):
                r[k] += int(res.get(k, 0) or 0)
            ipo = event.get("ipo")
            if ipo:
                key = reg + "|" + str(ipo)[:60]
                d["ipos"][key] = d["ipos"].get(key, 0) + 1
        _save(s)


def stats(days: int = 14) -> dict:
    """Aggregate the last `days` days for the admin dashboard."""
    days = max(1, min(int(days or 14), 90))
    with _lock:
        s = _load()
    today = datetime.now(timezone.utc).date()
    labels = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]

    series = []
    country, device, reg = {}, {}, {}
    ipos = {}
    for day in labels:
        dd = s["days"].get(day, {})
        series.append({
            "date": day,
            "pageviews": dd.get("pageviews", 0),
            "visits": dd.get("visits", 0),
            "checks": dd.get("checks", 0),
            "pans": dd.get("pans", 0),
        })
        for k, v in (dd.get("country") or {}).items():
            country[k] = country.get(k, 0) + v
        for k, v in (dd.get("device") or {}).items():
            device[k] = device.get(k, 0) + v
        for rk, rv in (dd.get("reg") or {}).items():
            acc = reg.setdefault(rk, {"checks": 0, "ok": 0, "no": 0, "busy": 0, "err": 0})
            for m in acc:
                acc[m] += rv.get(m, 0)
        for k, v in (dd.get("ipos") or {}).items():
            ipos[k] = ipos.get(k, 0) + v

    def topn(dct, n=8):
        return sorted(({"key": k, "count": v} for k, v in dct.items()), key=lambda x: -x["count"])[:n]

    win = {"pageviews": 0, "visits": 0, "checks": 0, "pans": 0}
    for p in series:
        for k in win:
            win[k] += p[k]

    return {
        "range_days": days,
        "totals": s["totals"],
        "window": win,
        "today": series[-1] if series else None,
        "series": series,
        "country": topn(country, 12),
        "device": device,
        "registrars": reg,
        "top_ipos": [{"registrar": k.split("|", 1)[0], "ipo": k.split("|", 1)[1] if "|" in k else k, "count": v}
                     for k, v in sorted(ipos.items(), key=lambda x: -x[1])[:8]],
    }
