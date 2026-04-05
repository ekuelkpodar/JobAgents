#!/usr/bin/env python3
"""normalize_status.py - Standardize all job status values to the canonical list."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"

CANONICAL = {"new", "saved", "applied", "phone_screen", "interview", "offer", "rejected", "archived"}

# Map of common non-canonical values → canonical
STATUS_MAP = {
    "": "new",
    "none": "new",
    "active": "new",
    "bookmarked": "saved",
    "bookmark": "saved",
    "interested": "saved",
    "apply": "applied",
    "submitted": "applied",
    "application sent": "applied",
    "screening": "phone_screen",
    "phone": "phone_screen",
    "screen": "phone_screen",
    "interviewing": "interview",
    "offer received": "offer",
    "decline": "rejected",
    "declined": "rejected",
    "pass": "rejected",
    "no": "rejected",
    "closed": "archived",
    "expired": "archived",
    "hidden": "archived",
}


def normalize():
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT id, status FROM jobs").fetchall()
    updated = 0

    for job_id, status in rows:
        raw = (status or "").lower().strip()
        if raw in CANONICAL:
            continue
        canonical = STATUS_MAP.get(raw, "new")
        conn.execute("UPDATE jobs SET status=? WHERE id=?", [canonical, job_id])
        updated += 1

    conn.commit()
    conn.close()
    print(f"Normalized {updated} status values to canonical form.")
    print(f"Canonical statuses: {sorted(CANONICAL)}")


if __name__ == "__main__":
    normalize()
