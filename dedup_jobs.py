#!/usr/bin/env python3
"""dedup_jobs.py - Remove duplicate job entries from jobs.db.
Keeps the entry with the lowest ID (earliest insert) and removes duplicates.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"


def dedup():
    conn = sqlite3.connect(str(DB_PATH))
    total_before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    # Find duplicate URLs — keep the min(id) for each URL
    dupes = conn.execute("""
        SELECT url, COUNT(*) as cnt, MIN(id) as keep_id
        FROM jobs
        GROUP BY url
        HAVING cnt > 1
    """).fetchall()

    removed = 0
    for url, cnt, keep_id in dupes:
        deleted = conn.execute(
            "DELETE FROM jobs WHERE url=? AND id != ?", [url, keep_id]
        ).rowcount
        removed += deleted

    conn.commit()
    total_after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()

    print(f"{'─'*50}")
    print(f"  Deduplication complete")
    print(f"  Before : {total_before} jobs")
    print(f"  Removed: {removed} duplicates")
    print(f"  After  : {total_after} jobs")
    print(f"{'─'*50}")


if __name__ == "__main__":
    dedup()
