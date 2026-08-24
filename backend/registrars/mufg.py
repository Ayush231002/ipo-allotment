"""MUFG / Intime registrar adapter (https://in.mpms.mufg.com)."""
from __future__ import annotations
import http.cookiejar
import json
import re
import threading
import time
import urllib.error
import urllib.request

from .base import RegistrarAdapter, TTLCache, normalized_result, SSL_CTX, USER_AGENT

BASE = "https://in.mpms.mufg.com/Initial_Offer/"

# MUFG sits behind Akamai. Be a polite client: serialise upstream calls and
# keep a minimum gap between them so a traffic spike from our server does not
# look like a scraper (which would get the server IP throttled/blocked).
MIN_INTERVAL = 0.4  # seconds between upstream request sequences
# HTTP statuses that mean "slow down / blocked" rather than "no such PAN".
BUSY_CODES = {403, 429, 503, 502, 520, 521, 522}


class MufgAdapter(RegistrarAdapter):
    key = "mufg"
    label = "MUFG / Intime"
    note = "Formerly Link Intime. Mainboard & SME IPOs."
    site_url = "https://in.mpms.mufg.com/Initial_Offer/public-issues.html"

    def __init__(self):
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj),
            urllib.request.HTTPSHandler(context=SSL_CTX),
        )
        self._opener.addheaders = [("User-Agent", USER_AGENT)]
        self._lock = threading.Lock()
        self._primed = False
        self._companies = TTLCache(ttl_seconds=120)
        self._last_call = 0.0

    def _throttle(self):
        wait = MIN_INTERVAL - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def _prime(self):
        try:
            self._opener.open(BASE + "public-issues.html", timeout=25).read()
            self._primed = True
        except Exception:
            self._primed = False

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        req.add_header("Accept", "application/json")
        with self._opener.open(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))

    def list_companies(self) -> list[dict]:
        cached = self._companies.get()
        if cached is not None:
            return cached
        with self._lock:
            self._throttle()
            xml = self._post("IPO.aspx/GetDetails", {}).get("d", "")
        out = []
        for cid, name in re.findall(
            r"<company_id>(\d+)</company_id>\s*<companyname>(.*?)</companyname>", xml, re.S
        ):
            out.append({"id": cid, "name": re.sub(r"\s+", " ", name).strip()})
        return self._companies.set(out) if out else out  # don't cache empties

    def _busy(self):
        return {"error": "MUFG is busy right now — please try again in a bit, "
                         "or check directly on their site.",
                "busy": True, "site": self.site_url}

    @staticmethod
    def _table_fields(xml: str) -> dict | None:
        m = re.search(r"<Table>(.*?)</Table>", xml, re.S)
        if not m:
            return None
        return {t: v.strip() for t, v in re.findall(r"<(\w+)>(.*?)</\1>", m.group(1), re.S)}

    def check(self, client_id: str, pan: str) -> dict:
        with self._lock:
            if not self._primed:
                self._prime()
            for attempt in range(2):
                try:
                    self._throttle()
                    tok = self._post("IPO.aspx/generateToken", {}).get("d", "")
                    xml = self._post("IPO.aspx/SearchOnPan", {
                        "clientid": client_id, "PAN": pan,
                        "IFSC": "", "CHKVAL": "1", "token": tok,
                    }).get("d", "")
                    if "<Table>" not in xml:
                        return normalized_result(found=False)
                    f = self._table_fields(xml) or {}
                    return normalized_result(
                        found=True,
                        applied=f.get("SHARES", ""),
                        allotted=f.get("ALLOT", ""),
                        category=f.get("PEMNDG", ""),
                        refund=f.get("RFNDAMT", ""),
                        account=f.get("DPCLITID", ""),
                    )
                except urllib.error.HTTPError as he:
                    # Rate-limited / blocked by the registrar (or its CDN):
                    # surface a friendly "busy" state instead of a raw error.
                    if he.code in BUSY_CODES:
                        return self._busy()
                    if attempt == 0:
                        self._prime()
                        continue
                    return normalized_result(found=False, error="HTTP %d" % he.code)
                except Exception:
                    if attempt == 0:
                        self._prime()
                        continue
                    return self._busy()
