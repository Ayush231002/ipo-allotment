"""KFintech registrar adapter (https://ipostatus.kfintech.com)."""
from __future__ import annotations
import http.client
import json
import re

from .base import RegistrarAdapter, TTLCache, http_get_text, normalized_result, SSL_CTX, USER_AGENT

HOME = "https://ipostatus.kfintech.com/"
API_HOST = "0uz601ms56.execute-api.ap-south-1.amazonaws.com"
API_PATH = "/prod/api/query?type=pan"


DEFAULT_API_URL = "https://%s%s" % (API_HOST, API_PATH)


class KFintechAdapter(RegistrarAdapter):
    key = "kfintech"
    label = "KFintech"
    note = "KFintech-registered IPOs, NCDs and REITs."
    site_url = "https://ipostatus.kfintech.com/"

    def __init__(self):
        self._companies = TTLCache(ttl_seconds=300)
        # API URL is scraped live from the JS bundle (it can change), with a
        # sane default. Used both by our server-side check and by the browser
        # (via direct_info) so the client-side path stays current too.
        self._api_url = DEFAULT_API_URL

    def list_companies(self) -> list[dict]:
        cached = self._companies.get()
        if cached is not None:
            return cached
        # The company list is embedded in the site's JS bundle (whose name
        # is content-hashed), so read the homepage, find the bundle, extract it.
        home = http_get_text(HOME)
        m = re.search(r"main\.[a-z0-9]+\.js", home)
        if not m:
            return []  # transient — do NOT cache an empty list
        js = http_get_text(HOME + "static/js/" + m.group(0))
        # Keep the live API endpoint in sync (the execute-api id can change).
        murl = re.search(r"https://[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com/prod/api/query", js)
        if murl:
            self._api_url = murl.group(0) + "?type=pan"
        i = js.find("JSON.parse('[{\"clientId\"")
        if i == -1:
            return []  # transient — do NOT cache an empty list
        o = js.find("'[", i)
        e = js.find("]')", o)
        arr = json.loads(js[o + 1:e + 1])
        out = [{"id": c["clientId"], "name": c["name"]} for c in arr]
        return self._companies.set(out) if out else out

    def direct_info(self) -> dict | None:
        # KFintech's check API sends CORS `Access-Control-Allow-Origin: *`, so
        # the browser can call it directly. Return the last-known URL WITHOUT
        # scraping here — this keeps /api/registrars (page load) instant. The
        # URL is refreshed lazily when the company list loads; the default is
        # correct today, and if it ever goes stale the server proxy is the
        # fallback.
        return {"type": "kfintech", "url": self._api_url}

    def check(self, client_id: str, pan: str) -> dict:
        # The Lambda behind this API reads the header names in EXACT lowercase,
        # so we must send them verbatim (http.client preserves case; urllib
        # would title-case them and the backend would 502).
        conn = http.client.HTTPSConnection(API_HOST, timeout=25, context=SSL_CTX)
        try:
            conn.request("GET", API_PATH, headers={
                "reqparam": pan,
                "client_id": client_id,
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            })
            r = conn.getresponse()
            status = r.status
            body = r.read().decode("utf-8", "ignore")
        finally:
            conn.close()

        if status == 404:
            return normalized_result(found=False)
        if status != 200:
            return normalized_result(found=False, error="HTTP %d" % status)
        try:
            j = json.loads(body)
        except Exception:
            return normalized_result(found=False, error="bad response")

        d = j.get("data", j)
        if isinstance(d, dict) and "data" in d:
            d = d["data"]
        rec = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else None)
        if not rec:
            return normalized_result(found=False)
        return normalized_result(
            found=True,
            name=rec.get("Name", ""),
            applied=rec.get("App_Shares", ""),
            allotted=rec.get("All_Shares", ""),
            account=rec.get("DP_CLID", ""),
        )
