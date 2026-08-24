"""
Registrar adapter interface.

To add a NEW registrar in the future, create a file in this package that
subclasses `RegistrarAdapter`, implement `list_companies()` and
`check(client_id, pan)`, and register it in `__init__.py`. Nothing else in
the app needs to change — the API and the UI pick it up automatically.
"""
from __future__ import annotations
import ssl
import time
import urllib.request

# Shared TLS context and a browser-like UA for all adapters.
SSL_CTX = ssl.create_default_context()
USER_AGENT = "Mozilla/5.0 (compatible; AllotCheck/1.0)"


def normalized_result(
    found: bool,
    name: str = "",
    applied: str = "",
    allotted: str = "",
    category: str = "",
    refund: str = "",
    account: str = "",
    error: str | None = None,
) -> dict:
    """A registrar-agnostic result shape the frontend understands.

    Every adapter maps its own fields onto these keys. Missing fields are
    simply left blank, so different registrars can expose different data.
    """
    if error is not None:
        return {"error": error}
    out = {
        "found": found,
        "name": name or "",
        "applied": str(applied or ""),
        "allotted": str(allotted or ""),
        "category": category or "",
        "refund": str(refund or ""),
        "account": account or "",
    }
    return out


class TTLCache:
    """Tiny in-memory cache (per warm Lambda container / per process)."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._t = 0.0
        self._val = None

    def get(self):
        if self._val is not None and (time.time() - self._t) < self.ttl:
            return self._val
        return None

    def set(self, val):
        self._t = time.time()
        self._val = val
        return val


def http_get_text(url: str, headers: dict | None = None, timeout: int = 25) -> str:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=SSL_CTX))
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


class RegistrarAdapter:
    """Base class every registrar implements."""

    key: str = ""          # url-safe id, e.g. "kfintech"
    label: str = ""        # human name shown in UI, e.g. "KFintech"
    note: str = ""         # optional one-line hint for the UI
    site_url: str = ""     # public status page, shown to users on fallback

    def list_companies(self) -> list[dict]:
        """Return [{"id": <client id>, "name": <company name>}, ...]."""
        raise NotImplementedError

    def check(self, client_id: str, pan: str) -> dict:
        """Return `normalized_result(...)` for one PAN on one company."""
        raise NotImplementedError

    def direct_info(self) -> dict | None:
        """If the registrar's check API is CORS-open, return a recipe the
        browser can use to call it DIRECTLY (from each user's own IP), e.g.
        {"type": "kfintech", "url": "https://.../query?type=pan"}.

        Returning None means "always proxy through the server". Calling the
        registrar directly from the browser spreads traffic across users' IPs
        instead of hammering our single server IP — a big anti-block win.
        """
        return None

    def meta(self) -> dict:
        m = {"key": self.key, "label": self.label, "note": self.note, "site": self.site_url}
        d = self.direct_info()
        if d:
            m["direct"] = d
        return m
