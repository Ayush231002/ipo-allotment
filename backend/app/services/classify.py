"""Deterministic IPO status classification from dates.

Status is *derived*, never guessed: given open/close/allotment/listing dates and
today, the lifecycle stage is unambiguous. IPOs without enough dated metadata
stay 'unclassified' (honest) rather than being forced into a bucket.

ISO dates (YYYY-MM-DD) compare correctly as plain strings, so no date parsing is
needed for the ordering checks.
"""
from __future__ import annotations
from datetime import date

from .. import db

VALID = {"upcoming", "running", "closed", "listed", "unclassified"}


def status_from_dates(open_date: str, close_date: str, allotment_date: str,
                      listing_date: str, today: str) -> str:
    o = (open_date or "").strip()
    c = (close_date or "").strip()
    l = (listing_date or "").strip()

    if not o and not l:
        return "unclassified"          # not enough to place it on the timeline
    if l and today >= l:
        return "listed"
    if c and today > c:
        return "closed"                # bidding done, awaiting listing
    if o and today >= o and (not c or today <= c):
        return "running"
    if o and today < o:
        return "upcoming"
    return "unclassified"


def classify_row(row: dict, today: str | None = None) -> str:
    today = today or date.today().isoformat()
    return status_from_dates(
        row.get("open_date", ""), row.get("close_date", ""),
        row.get("allotment_date", ""), row.get("listing_date", ""), today)


def reclassify_all(today: str | None = None) -> dict:
    """Recompute status for every dated IPO. Returns a change summary.

    IPOs whose status was set manually to a non-derivable value are left alone
    only when they have no dates; once dated, the derived status is authoritative.
    """
    today = today or date.today().isoformat()
    rows = db.query(
        "SELECT id, status, open_date, close_date, allotment_date, listing_date FROM ipo")
    changed = 0
    counts = {"upcoming": 0, "running": 0, "closed": 0, "listed": 0, "unclassified": 0}
    for r in rows:
        new = classify_row(r, today)
        counts[new] += 1
        if new != r["status"] and new != "unclassified":
            db.execute("UPDATE ipo SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (new, r["id"]))
            changed += 1
    return {"changed": changed, "counts": counts, "as_of": today}
