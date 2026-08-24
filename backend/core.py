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
import json
import os
import re

import registrars
import analytics

ADMIN_TOKEN = os.environ.get("ALLOTCHECK_ADMIN_TOKEN", "changeme")


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

    # ---- analytics beacon ----
    if path == "/api/track":
        if method != "POST":
            return 405, {"error": "POST only"}
        try:
            event = body if isinstance(body, dict) else json.loads(body or "{}")
        except Exception:
            event = {}
        country = headers.get("cloudfront-viewer-country") or headers.get("x-country") or "??"
        device = _device_from_ua(headers.get("user-agent", ""))
        analytics.track(event, country=country, device=device)
        return 200, {"ok": True}

    # ---- admin stats (token protected) ----
    if path == "/api/admin/stats":
        token = (params.get("token") or headers.get("x-admin-token") or "")
        if token != ADMIN_TOKEN:
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
        client_id = (params.get("clientid") or "").strip()
        pan = (params.get("pan") or "").strip().upper()
        if not client_id or not pan:
            return 400, {"error": "clientid and pan are required"}
        return 200, adapter.check(client_id, pan)
    except Exception as e:
        return 200, {"error": str(e)[:80]}
