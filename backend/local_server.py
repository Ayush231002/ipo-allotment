"""
Local development server.

Serves the static frontend from ../web AND the same API that Lambda serves,
so you can run and test the whole product — including analytics + the admin
dashboard — on your machine exactly as it will behave in AWS.

    cd backend
    python local_server.py

Admin dashboard: http://localhost:8080/admin  (token: env ALLOTCHECK_ADMIN_TOKEN,
default "changeme").
"""
import json
import os
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from core import handle_api

PORT = 8080
WEB_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "web"))
_MIME = {".html": "text/html; charset=utf-8", ".css": "text/css",
         ".js": "application/javascript", ".svg": "image/svg+xml",
         ".png": "image/png", ".json": "application/json", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _headers_dict(self):
        return {k: v for k, v in self.headers.items()}

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _api(self, method, u, body=None):
        params = {k: v[0] for k, v in parse_qs(u.query).items()}
        status, resp = handle_api(method, u.path, params, self._headers_dict(), body)
        self._send(status, json.dumps(resp))

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", "ignore") if length else ""
        if u.path.startswith("/api/"):
            return self._api("POST", u, body)
        self._send(404, "not found", "text/plain")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            return self._api("GET", u)
        # static files (with /admin -> admin.html convenience route)
        rel = u.path.lstrip("/") or "index.html"
        if rel == "admin":
            rel = "admin.html"
        full = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            full = os.path.join(WEB_DIR, "index.html")
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as fp:
            self._send(200, fp.read(), _MIME.get(ext, "application/octet-stream"))


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"


def main():
    ip = lan_ip()
    print("=" * 56)
    print("  AllotCheck (local dev) is running")
    print("  App    :  http://localhost:%d/" % PORT)
    print("  Admin  :  http://localhost:%d/admin" % PORT)
    print("  Phone  :  http://%s:%d/" % (ip, PORT))
    print()
    print("  Stop: close this window or press Ctrl+C.")
    print("=" * 56)
    try:
        webbrowser.open("http://localhost:%d/" % PORT)
    except Exception:
        pass
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
