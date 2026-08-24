"""Lightweight in-process scheduler.

Phase 2 runs one internal job — status reclassification — on an interval. It
makes NO external calls, so it is safe to run inside the web process on Render's
free tier. Official auto-fetchers, when enabled, register here later.

Started from the app lifespan; stops cleanly on shutdown. Never started at
import time (so tests don't spawn threads).
"""
from __future__ import annotations
import threading
import time

from .. import config, db
from . import classify

_thread: threading.Thread | None = None
_stop = threading.Event()


def _log(source_key: str, ok: bool, message: str) -> None:
    try:
        db.execute("INSERT INTO source_fetch_logs (source_id, ok, message) VALUES (?,?,?)",
                   (db.source_id(source_key), 1 if ok else 0, message[:240]))
    except Exception:
        pass  # logging must never crash the loop


def run_once() -> dict:
    """Run the internal jobs a single time (also exposed to admin for on-demand)."""
    result = classify.reclassify_all()
    _log("manual", True, f"classify: {result['changed']} changed, counts={result['counts']}")
    return result


def _loop() -> None:
    # small initial delay so startup stays fast
    if _stop.wait(5):
        return
    while not _stop.is_set():
        try:
            run_once()
        except Exception as e:
            _log("manual", False, f"scheduler error: {e}")
        _stop.wait(max(60, config.CLASSIFY_INTERVAL_SECONDS))


def start() -> None:
    global _thread
    if not config.SCHEDULER_ENABLED or (_thread and _thread.is_alive()):
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="allotcheck-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
