"""Bridge to the existing privacy-first checker.

The checker (core.handle_api + registrars/ + analytics) is reused UNCHANGED.
FastAPI hands it the same (method, path, params, headers, body) tuple the AWS
Lambda and the dev server pass, so the multi-PAN allotment flow behaves
identically. This is the "do not break the checker" guarantee, in code.
"""
from __future__ import annotations
import os
import sys

# core.py / registrars / analytics live in backend/ (one level up), and import
# each other as top-level modules — put that dir on the path.
_BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import core  # noqa: E402  (path set above)


def handle(method: str, path: str, params: dict, headers: dict, body):
    return core.handle_api(method, path, params, headers, body)
