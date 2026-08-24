"""
Framework-agnostic API core.

`handle_api(method, path, params, headers, body)` returns
(status_code, json_serialisable_obj). Both the AWS Lambda handler and the local
dev server call this, so the business logic is written and tested once.

Routes:
  GET  /api/registrars                        -> [{key,label,note,site,direct?}]
  GET  /api/<key>/companies                   -> [{id,name}]
  GET  /api/<key>/check?clientid=..&pan=..    -> normalized result
  POST /api/track                             -> {ok:true}   (anonymous analytics beacon)
  GET  /api/admin/stats?token=..&days=..      -> aggregate stats (token-protected)
"""
from __future__ import annotations
import hmac
import json
import os
import re
import threading
import time
from collections import defaultdict, deque

import registrars
import analytics

# Admin auth. The token MUST be provided via env; the old default of "changeme"
# is treated as "admin disabled" so a misconfigured deploy never ships an
# accessible dashboard. Never hard-code this value anywhere in the repo.
_ADMIN_TOKEN = (os.environ.get("ALLOTCHECK_ADMIN_TOKEN") or "").strip()
_ADMIN_ENABLED = bool(_ADMIN_TOKEN) and _ADMIN_TOKEN != "changeme"

# --- lightweight per-IP rate limiting (first layer; per-process only) ---
# NOTE: resets on restart and is NOT shared across Render instances / Lambda
# containers. It caps abuse from a single client per process; the real global
# cap belongs at the edge (API Gateway usage plan / WAF / Render). See
# docs/ARCHITECTURE.md.
_RL_LOCK = threading.Lock()
_rl_hits: dict[str, deque] = defaultdict(deque)
_RL_LIMITS = {"check": 60, "track": 120}  # requests per 60s window per IP


def _client_ip(headers: dict) -> str:
    xff = headers.get("x-forwarded-for") or ""
    if xff:
        return xff.split(",")[0].strip()
    return headers.get("x-real-ip") or "?"


def _rate_ok(ip: str, bucket: str, window: int = 60) -> bool:
    limit = _RL_LIMITS.get(bucket, 60)
    now = time.time()
    key = bucket + "|" + ip
    with _RL_LOCK:
        dq = _rl_hits[key]
        while dq and dq[0] <= now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        # opportunistic cleanup so idle keys don't accumulate forever
        if len(_rl_hits) > 5000:
            for k in [k for k, v in list(_rl_hits.items()) if not v]:
                _rl_hits.pop(k, None)
        return True


def _device_from_ua(ua: str) -> str:
    ua = (ua or "").lower()
    if any(x in ua for x in ("ipad", "tablet")):
        return "tablet"
    if any(x in ua for x in ("mobi", "android", "iphone", "ipod")):
        return "mobile"
    return "desktop"


def handle_api(method: str, path: str, params: dict, headers: dict | None = None, body=None):
    method = (method or "GET").upper()
    headers = {(k or "").lower(): v for k, v in (headers or {}).items()}
    path = "/" + path.strip("/")

    ip = _client_ip(headers)

    # ---- analytics beacon ----
    if path == "/api/track":
        if method != "POST":
            return 405, {"error": "POST only"}
        if not _rate_ok(ip, "track"):
            return 429, {"error": "rate limited"}
        try:
            event = body if isinstance(body, dict) else json.loads(body or "{}")
        except Exception:
            event = {}
        country = headers.get("cloudfront-viewer-country") or headers.get("x-country") or "??"
        device = _device_from_ua(headers.get("user-agent", ""))
        analytics.track(event, country=country, device=device)
        return 200, {"ok": True}

    # ---- admin stats (token protected, header-only, constant-time) ----
    if path == "/api/admin/stats":
        if not _ADMIN_ENABLED:
            return 503, {"error": "admin disabled: set ALLOTCHECK_ADMIN_TOKEN"}
        # Header only — never accept the token in the query string (it would
        # leak into access logs, proxies and browser history).
        token = headers.get("x-admin-token") or ""
        if not hmac.compare_digest(token, _ADMIN_TOKEN):
            return 401, {"error": "unauthorized"}
        try:
            days = int(params.get("days") or 14)
        except Exception:
            days = 14
        return 200, analytics.stats(days)

    # ---- registrar list ----
    if path == "/api/registrars":
        return 200, registrars.list_registrars()

    # ---- registrar company list / check ----
    m = re.match(r"^/api/([a-z0-9_-]+)/(companies|check)$", path)
    if not m:
        return 404, {"error": "not found"}
    key, action = m.group(1), m.group(2)
    adapter = registrars.get(key)
    if adapter is None:
        return 404, {"error": "unknown registrar: %s" % key}
    try:
        if action == "companies":
            return 200, adapter.list_companies()
        if not _rate_ok(ip, "check"):
            return 429, {"error": "rate limited"}
        client_id = (params.get("clientid") or "").strip()
        pan = (params.get("pan") or "").strip().upper()
        if not client_id or not pan:
            return 400, {"error": "clientid and pan are required"}
        return 200, adapter.check(client_id, pan)
    except Exception as e:
        return 200, {"error": str(e)[:80]}
