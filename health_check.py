#!/usr/bin/env python3
"""health_check.py - Pipeline health reporter.
Runs automatically after fetch_jobs.py to surface data quality issues.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests

DB_PATH  = Path(__file__).parent / "jobs.db"
LOG_FILE = Path(__file__).parent / "fetch_errors.log"


def check():
    conn = sqlite3.connect(str(DB_PATH))
    now  = datetime.now(timezone.utc)

    total     = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    no_grade  = conn.execute("SELECT COUNT(*) FROM jobs WHERE grade IS NULL").fetchone()[0]
    no_desc   = conn.execute("SELECT COUNT(*) FROM jobs WHERE description IS NULL OR description=''").fetchone()[0]
    no_date   = conn.execute("SELECT COUNT(*) FROM jobs WHERE published_date IS NULL OR published_date=''").fetchone()[0]

    by_grade  = dict(conn.execute("SELECT COALESCE(grade,'—'), COUNT(*) FROM jobs GROUP BY grade ORDER BY grade").fetchall())
    by_status = dict(conn.execute("SELECT COALESCE(status,'new'), COUNT(*) FROM jobs GROUP BY status ORDER BY status").fetchall())
    by_source = conn.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10").fetchall()

    week_new  = conn.execute("SELECT COUNT(*) FROM jobs WHERE fetched_at >= date('now','-7 days')").fetchone()[0]
    applied   = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='applied'").fetchone()[0]
    interviews= conn.execute("SELECT COUNT(*) FROM jobs WHERE status='interview'").fetchone()[0]
    offers    = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='offer'").fetchone()[0]

    conn.close()

    # Count error log lines
    error_count = 0
    if LOG_FILE.exists():
        error_count = sum(1 for _ in LOG_FILE.open())

    print(f"\n{'━'*56}")
    print(f"  JobAgent Health Check  ·  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'━'*56}")
    print(f"  Total jobs in DB   : {total:,}")
    print(f"  Added this week    : {week_new:,}")
    print(f"  Jobs without grade : {no_grade:,}  {'⚠️  run Evaluate All' if no_grade > 50 else '✅'}")
    print(f"  Jobs without desc  : {no_desc:,}")
    print(f"  Jobs without date  : {no_date:,}")
    print(f"  RSS fetch errors   : {error_count}")
    print()
    print(f"  Pipeline status:")
    print(f"    Applied    : {applied:,}")
    print(f"    Interviews : {interviews:,}")
    print(f"    Offers     : {offers:,}")
    print()
    print(f"  Grade distribution:")
    for grade, cnt in sorted(by_grade.items()):
        bar = "█" * min(20, cnt // max(1, total // 20))
        print(f"    {grade:4s}  {cnt:5,d}  {bar}")
    print()
    print(f"  Status distribution:")
    for st, cnt in sorted(by_status.items()):
        print(f"    {st:15s}  {cnt:5,d}")
    print()
    print(f"  Top sources:")
    for src, cnt in by_source:
        print(f"    {(src or 'Unknown'):30s}  {cnt:5,d}")
    print(f"{'━'*56}")

    # Recommendations
    issues = []
    if no_grade > 50:
        issues.append(f"  ⚠️  {no_grade} jobs need grading — run: POST /api/evaluate-all")
    if error_count > 20:
        issues.append(f"  ⚠️  {error_count} RSS errors — check fetch_errors.log")
    if total == 0:
        issues.append("  ⚠️  No jobs in DB — run: python fetch_jobs.py")

    if issues:
        print("\n  Action items:")
        for i in issues:
            print(i)
        print()


if __name__ == "__main__":
    check()
