# JobAgent — Local Remote Tech Job Aggregator

A fully local RSS job aggregator that pulls listings from 100 tech job feeds and serves a dark-mode, filterable dashboard at `http://localhost:5000`.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![Flask](https://img.shields.io/badge/Flask-3.1-green) ![SQLite](https://img.shields.io/badge/Database-SQLite-orange)

---

## Features

- Aggregates **100 RSS feeds** across Engineering, AI/ML, DevOps, Data Science, Security, Design, Marketing, Web3, and more
- Stores all jobs locally in **SQLite** — no external services or API keys needed
- **Dark-mode dashboard** with live search, category/source filters, date range, and sorting
- **Resilient fetcher** — skips failed feeds and logs errors, never crashes mid-run
- Re-runnable: subsequent fetches update existing records and add new ones

---

## Quickstart

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Fetch jobs (~5–10 min on first run)
```bash
python fetch_jobs.py
```
Reads all feeds from `Tech_Job_RSS_Feeds.xlsx`, stores results in `jobs.db`. Feed errors are logged to `fetch_errors.log` and skipped automatically.

### 3. Start the dashboard
```bash
python app.py
```
Open **http://localhost:5000** in your browser.

---

## Dashboard

| Feature | Detail |
|---|---|
| Live search | Filters by title, description, source as you type |
| Category filter | Checkbox multi-select (Engineering, AI/ML, DevOps, etc.) |
| Source filter | Checkbox multi-select per RSS source |
| Date range | Today / Last 7 days / Last 30 days / All time |
| Sort | Newest first, Oldest first, Source A–Z |
| Pagination | 200 cards loaded at a time with "Load more" |
| Relative timestamps | "2h ago", "3d ago" |

---

## Project Structure

```
JobAgent/
├── fetch_jobs.py          # RSS fetcher — reads XLSX, populates jobs.db
├── app.py                 # Flask server + embedded HTML/CSS/JS dashboard
├── requirements.txt       # Python dependencies
├── Tech_Job_RSS_Feeds.xlsx  # 100 RSS feed URLs with source/category metadata
└── README.md
```

> `jobs.db` and `fetch_errors.log` are generated at runtime and excluded from version control.

---

## Dependencies

```
feedparser   — RSS/Atom feed parsing
flask        — Web server
openpyxl     — Read .xlsx feed list
requests     — HTTP fetching with timeout support
```

---

## Notes

- ~55 of 100 feeds are currently active; the rest return 404/403/410 (dead or blocked URLs)
- Indeed and Upwork RSS feeds are blocked; Dice RSS endpoints are defunct
- Run `fetch_jobs.py` on a schedule (e.g. daily cron) to keep jobs fresh
