#!/usr/bin/env python3
"""
fetch_jobs.py - RSS job aggregator fetcher
Reads RSS feeds from Tech_Job_RSS_Feeds.xlsx and stores jobs in jobs.db
"""

import sqlite3
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import openpyxl
import requests

# ── Configuration ────────────────────────────────────────────────────────────
XLSX_PATH   = Path(__file__).parent / "Tech_Job_RSS_Feeds.xlsx"
DB_PATH     = Path(__file__).parent / "jobs.db"
ERROR_LOG   = Path(__file__).parent / "fetch_errors.log"
JOBS_PER_FEED = 25
REQUEST_DELAY = 0.5   # seconds between requests

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=str(ERROR_LOG),
    level=logging.ERROR,
    format="%(asctime)s  %(levelname)s  %(message)s",
)

# ── Database setup ────────────────────────────────────────────────────────────
def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            title         TEXT,
            url           TEXT UNIQUE,
            published_date TEXT,
            source        TEXT,
            feed_name     TEXT,
            category      TEXT,
            description   TEXT,
            fetched_at    TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON jobs(url)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON jobs(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON jobs(source)")
    conn.commit()


def upsert_job(conn: sqlite3.Connection, job: dict) -> None:
    conn.execute("""
        INSERT INTO jobs (title, url, published_date, source, feed_name,
                          category, description, fetched_at)
        VALUES (:title, :url, :published_date, :source, :feed_name,
                :category, :description, :fetched_at)
        ON CONFLICT(url) DO UPDATE SET
            title          = excluded.title,
            published_date = excluded.published_date,
            source         = excluded.source,
            feed_name      = excluded.feed_name,
            category       = excluded.category,
            description    = excluded.description,
            fetched_at     = excluded.fetched_at
    """, job)


# ── Excel reader ──────────────────────────────────────────────────────────────
def load_feeds() -> list[dict]:
    wb = openpyxl.load_workbook(str(XLSX_PATH), read_only=True, data_only=True)
    ws = wb["All Feeds"]
    feeds = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        num, source, feed_name, rss_url, category, status = (row + (None,) * 6)[:6]
        if rss_url and str(rss_url).startswith("http"):
            feeds.append({
                "source":    str(source).strip()    if source    else "Unknown",
                "feed_name": str(feed_name).strip() if feed_name else "Unknown",
                "url":       str(rss_url).strip(),
                "category":  str(category).strip()  if category  else "General",
            })
    wb.close()
    return feeds


# ── Date helpers ──────────────────────────────────────────────────────────────
def parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


# ── Main fetcher ──────────────────────────────────────────────────────────────
def fetch_feed(feed: dict) -> list[dict]:
    """Fetch a single RSS feed and return a list of job dicts."""
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
    # Fetch raw bytes with a timeout so we never hang indefinitely
    resp = requests.get(
        feed["url"],
        headers={"User-Agent": ua, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"},
        timeout=15,
        allow_redirects=True,
    )
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)

    if parsed.get("bozo") and not parsed.get("entries"):
        exc = parsed.get("bozo_exception")
        raise ValueError(f"Feed parse error: {exc}")

    jobs = []
    now = datetime.now(timezone.utc).isoformat()

    for entry in parsed.entries[:JOBS_PER_FEED]:
        title = getattr(entry, "title", "").strip() or "(no title)"
        url   = getattr(entry, "link",  "").strip()
        if not url:
            continue  # skip entries without a URL

        raw_desc = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        # Strip basic HTML tags for preview
        import re
        clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()[:500]

        jobs.append({
            "title":          title,
            "url":            url,
            "published_date": parse_date(entry),
            "source":         feed["source"],
            "feed_name":      feed["feed_name"],
            "category":       feed["category"],
            "description":    clean_desc,
            "fetched_at":     now,
        })

    return jobs


def main() -> None:
    feeds = load_feeds()
    print(f"\n{'─'*60}")
    print(f"  JobAgent RSS Fetcher")
    print(f"  Feeds loaded: {len(feeds)}")
    print(f"{'─'*60}\n")

    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)

    total_attempted = 0
    total_succeeded = 0
    total_failed    = 0
    total_jobs      = 0

    for i, feed in enumerate(feeds, 1):
        total_attempted += 1
        label = f"[{i:3d}/{len(feeds)}] {feed['feed_name']} ({feed['source']})"
        print(f"Fetching {label}... ", end="", flush=True)

        try:
            jobs = fetch_feed(feed)
            for job in jobs:
                upsert_job(conn, job)
            conn.commit()
            total_succeeded += 1
            total_jobs      += len(jobs)
            print(f"got {len(jobs)} jobs")
        except Exception as exc:
            total_failed += 1
            msg = f"FAILED: {feed['source']} / {feed['feed_name']} ({feed['url']}): {exc}"
            print(f"FAILED — {exc}")
            logging.error(msg)

        time.sleep(REQUEST_DELAY)

    # Final tally from DB
    (stored_total,) = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
    conn.close()

    print(f"\n{'─'*60}")
    print(f"  Feeds attempted : {total_attempted}")
    print(f"  Feeds succeeded : {total_succeeded}")
    print(f"  Feeds failed    : {total_failed}")
    print(f"  Jobs this run   : {total_jobs}")
    print(f"  Total in DB     : {stored_total}")
    print(f"  Errors logged   : {ERROR_LOG}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
    # Auto-run health check after fetch
    try:
        import health_check
        health_check.check()
    except Exception:
        pass
