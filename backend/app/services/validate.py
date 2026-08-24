"""Data validation pipeline.

Runs before financial data is persisted/displayed: format checks, plausible
ranges, impossible-value and ordering detection. Issues are returned to the
caller and recorded in `data_validation_issues` so the data-quality view and
admin panel can surface them instead of silently accepting bad data.
"""
from __future__ import annotations
import re

from .. import db

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _issue(field: str, severity: str, detail: str) -> dict:
    return {"field": field, "severity": severity, "detail": detail}


def validate_ipo(payload: dict) -> list[dict]:
    """Validate dated metadata + price band. Returns a list of issues (may be
    empty). `error` issues should block persistence; `warn` are advisory."""
    issues: list[dict] = []

    for f in ("open_date", "close_date", "allotment_date", "listing_date"):
        v = (payload.get(f) or "").strip()
        if v and not _DATE_RE.match(v):
            issues.append(_issue(f, "error", f"{f} must be YYYY-MM-DD (got '{v}')"))

    # ordering (only compares the ones present + well-formed)
    order = [("open_date", "close_date"), ("close_date", "allotment_date"),
             ("allotment_date", "listing_date")]
    for a, b in order:
        va, vb = (payload.get(a) or "").strip(), (payload.get(b) or "").strip()
        if _DATE_RE.match(va or "") and _DATE_RE.match(vb or "") and va > vb:
            issues.append(_issue(b, "warn", f"{b} ({vb}) is before {a} ({va})"))

    pmin, pmax = payload.get("price_min"), payload.get("price_max")
    for name, val in (("price_min", pmin), ("price_max", pmax)):
        if val is not None and (not isinstance(val, (int, float)) or val <= 0):
            issues.append(_issue(name, "error", f"{name} must be a positive number"))
    if isinstance(pmin, (int, float)) and isinstance(pmax, (int, float)) and pmin > pmax:
        issues.append(_issue("price_min", "error", f"price_min ({pmin}) > price_max ({pmax})"))

    lot = payload.get("lot_size")
    if lot is not None and (not isinstance(lot, int) or lot <= 0):
        issues.append(_issue("lot_size", "error", "lot_size must be a positive integer"))

    size = payload.get("issue_size_cr")
    if size is not None and (not isinstance(size, (int, float)) or size <= 0):
        issues.append(_issue("issue_size_cr", "error", "issue_size_cr must be positive"))

    board = (payload.get("board") or "").strip().lower()
    if board and board not in ("mainboard", "sme", "unknown"):
        issues.append(_issue("board", "warn", f"unexpected board '{board}'"))

    return issues


def validate_subscription(payload: dict) -> list[dict]:
    issues: list[dict] = []
    for f in ("overall_x", "qib_x", "nii_x", "retail_x", "employee_x", "shareholder_x"):
        v = payload.get(f)
        if v is not None and (not isinstance(v, (int, float)) or v < 0):
            issues.append(_issue(f, "error", f"{f} must be >= 0"))
    if all(payload.get(f) is None for f in ("overall_x", "qib_x", "nii_x", "retail_x")):
        issues.append(_issue("subscription", "error", "at least one subscription figure is required"))
    return issues


def has_errors(issues: list[dict]) -> bool:
    return any(i["severity"] == "error" for i in issues)


def record(ipo_id: int | None, issues: list[dict]) -> None:
    """Replace the stored issues for one IPO with the current set."""
    if ipo_id is not None:
        db.execute("DELETE FROM data_validation_issues WHERE ipo_id=?", (ipo_id,))
    for i in issues:
        db.execute(
            "INSERT INTO data_validation_issues (ipo_id, field, severity, detail) "
            "VALUES (?,?,?,?)", (ipo_id, i["field"], i["severity"], i["detail"]))
