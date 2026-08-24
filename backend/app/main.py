"""AllotCheck intelligence platform — FastAPI entrypoint.

  uvicorn app.main:app --host 0.0.0.0 --port $PORT   (run from backend/)

Route map:
  /api/v1/*   -> intelligence read model (this package)
  /api/*      -> existing checker, reused verbatim via app.legacy
  /assets/*   -> static SPA assets
  /, /dashboard, /ipo/{slug}, /admin -> SPA HTML pages
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, db, legacy
from .routers import meta, ipos, admin as admin_router
from .services import scheduler


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    db.init_db()          # run migrations + seed the source registry
    scheduler.start()     # internal classification job (no external calls)
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(title="AllotCheck Intelligence", version="1.0.0-phase1",
              docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json",
              lifespan=lifespan)


# ---- security headers on every response (mirrors the dev server) ----
@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    ctype = resp.headers.get("content-type", "")
    if "text/html" in ctype:
        resp.headers["Content-Security-Policy"] = config.CSP
    return resp


# ---- v1 intelligence API (registered BEFORE the legacy catch-all) ----
app.include_router(meta.router, prefix="/api/v1", tags=["meta"])
app.include_router(ipos.router, prefix="/api/v1", tags=["ipos"])
app.include_router(admin_router.router, prefix="/api/v1", tags=["admin"])


# ---- legacy checker: every other /api/* path -> core.handle_api unchanged ----
@app.api_route("/api/{path:path}", methods=["GET", "POST"])
async def legacy_bridge(path: str, request: Request):
    if path == "v1" or path.startswith("v1/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    body = None
    if request.method == "POST":
        body = (await request.body()).decode("utf-8", "ignore") or ""
    params = dict(request.query_params)
    headers = {k.lower(): v for k, v in request.headers.items()}
    status, obj = legacy.handle(request.method, "/api/" + path, params, headers, body)
    return JSONResponse(obj, status_code=status,
                        headers={"Cache-Control": "no-store"})


# ---- SPA pages (pretty routes) ----
def _page(name: str) -> FileResponse:
    return FileResponse(os.path.join(config.WEB_DIR, name), media_type="text/html")


@app.get("/")
def home():
    return _page("index.html")


@app.get("/dashboard")
def dashboard_page():
    return _page("dashboard.html")


@app.get("/ipo/{slug}")
def ipo_page(slug: str):
    # SPA reads the slug from the URL; one HTML file serves every IPO.
    return _page("ipo.html")


@app.get("/admin")
def admin_page():
    return _page("admin.html")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


# ---- static assets (mounted last so it never shadows the routes above) ----
app.mount("/assets", StaticFiles(directory=os.path.join(config.WEB_DIR, "assets")),
          name="assets")
