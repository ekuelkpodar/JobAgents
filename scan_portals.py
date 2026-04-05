#!/usr/bin/env python3
"""scan_portals.py - Career portal scanner for direct company job listings.
Reads config/portals.yml and scrapes Greenhouse, Ashby, Lever APIs.
"""

import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

DB_PATH    = Path(__file__).parent / "jobs.db"
CONFIG     = Path(__file__).parent / "config" / "portals.yml"
LOG_FILE   = Path(__file__).parent / "scan_results.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_config() -> dict:
    with open(CONFIG, "r") as f:
        return yaml.safe_load(f)


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()[:500]


def is_relevant(title: str, role_filters: list[str]) -> bool:
    t = title.lower()
    return any(kw in t for kw in role_filters)


def fetch_greenhouse(slug: str, company_name: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for job in data.get("jobs", []):
            jobs.append({
                "title":          job.get("title", ""),
                "url":            job.get("absolute_url", ""),
                "description":    clean_html(job.get("content", "")),
                "source":         company_name,
                "feed_name":      f"{company_name} (Greenhouse)",
                "category":       "Engineering",
                "published_date": job.get("updated_at", datetime.now(timezone.utc).isoformat()),
                "fetched_at":     datetime.now(timezone.utc).isoformat(),
                "location":       (job.get("location") or {}).get("name", ""),
            })
        return jobs
    except Exception as e:
        logging.error(f"Greenhouse {slug}: {e}")
        return []


def fetch_ashby(slug: str, company_name: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for job in data.get("jobs", []):
            jobs.append({
                "title":          job.get("title", ""),
                "url":            job.get("jobUrl", f"https://jobs.ashby.com/{slug}/{job.get('id','')}"),
                "description":    clean_html(job.get("descriptionHtml", job.get("description", ""))),
                "source":         company_name,
                "feed_name":      f"{company_name} (Ashby)",
                "category":       "Engineering",
                "published_date": job.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                "fetched_at":     datetime.now(timezone.utc).isoformat(),
                "location":       (job.get("location") or ""),
            })
        return jobs
    except Exception as e:
        logging.error(f"Ashby {slug}: {e}")
        return []


def fetch_lever(slug: str, company_name: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for job in data:
            desc_parts = [
                clean_html(s.get("content", ""))
                for s in job.get("lists", []) + [{"content": job.get("descriptionPlain", "")}]
            ]
            jobs.append({
                "title":          job.get("text", ""),
                "url":            job.get("hostedUrl", ""),
                "description":    " ".join(desc_parts)[:500],
                "source":         company_name,
                "feed_name":      f"{company_name} (Lever)",
                "category":       "Engineering",
                "published_date": datetime.fromtimestamp(
                    job.get("createdAt", time.time()) / 1000, tz=timezone.utc
                ).isoformat(),
                "fetched_at":     datetime.now(timezone.utc).isoformat(),
                "location":       (job.get("categories") or {}).get("location", ""),
            })
        return jobs
    except Exception as e:
        logging.error(f"Lever {slug}: {e}")
        return []


def upsert_job(conn: sqlite3.Connection, job: dict) -> bool:
    """Insert job, skip if URL already exists. Returns True if new."""
    if not job.get("url"):
        return False
    existing = conn.execute("SELECT id FROM jobs WHERE url=?", [job["url"]]).fetchone()
    if existing:
        return False
    conn.execute("""
        INSERT INTO jobs (title, url, published_date, source, feed_name, category,
                          description, fetched_at, location)
        VALUES (:title, :url, :published_date, :source, :feed_name, :category,
                :description, :fetched_at, :location)
    """, job)
    return True


def main():
    config = load_config()
    role_filters = config.get("role_filters", [])
    ats_urls = config.get("ats_urls", {})

    conn = get_db()
    total_new = 0
    total_skipped = 0

    all_companies = []
    for group_key, companies in config.items():
        if group_key in ("ats_urls", "role_filters"):
            continue
        if isinstance(companies, list):
            all_companies.extend(companies)

    print(f"\n{'─'*60}")
    print(f"  JobAgent Portal Scanner")
    print(f"  Companies to scan: {len(all_companies)}")
    print(f"{'─'*60}\n")

    for company in all_companies:
        name     = company["name"]
        platform = company["platform"]
        slug     = company["slug"]

        print(f"Scanning {name} ({platform})... ", end="", flush=True)
        logging.info(f"Scanning {name} ({platform}/{slug})")

        if platform == "greenhouse":
            jobs = fetch_greenhouse(slug, name)
        elif platform == "ashby":
            jobs = fetch_ashby(slug, name)
        elif platform == "lever":
            jobs = fetch_lever(slug, name)
        else:
            print(f"Unknown platform: {platform}")
            continue

        relevant = [j for j in jobs if is_relevant(j["title"], role_filters)]
        new_count = 0
        for job in relevant:
            if upsert_job(conn, job):
                new_count += 1
            else:
                total_skipped += 1
        conn.commit()
        total_new += new_count
        print(f"{len(jobs)} total, {len(relevant)} relevant, {new_count} new")
        logging.info(f"{name}: {new_count} new jobs")
        time.sleep(0.5)

    conn.close()
    print(f"\n{'─'*60}")
    print(f"  New jobs added  : {total_new}")
    print(f"  Already in DB   : {total_skipped}")
    print(f"  Log             : {LOG_FILE}")
    print(f"{'─'*60}\n")
    logging.info(f"Scan complete: {total_new} new, {total_skipped} existing")


if __name__ == "__main__":
    main()
