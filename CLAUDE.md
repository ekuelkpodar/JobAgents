# JobAgent v2 — Agent Instructions

## What this project does
RSS-based job aggregator + AI evaluation pipeline + auto-apply system.
- Pulls from 100+ RSS feeds (Tech_Job_RSS_Feeds.xlsx)
- Scores jobs against your resume using Claude API (A-F grades across 10 dimensions)
- Classifies jobs into archetypes (AI/ML, DevOps, PM, etc.)
- Generates ATS-optimized tailored CVs per job via Playwright PDF
- Scans company career portals directly (Greenhouse, Ashby, Lever)
- Auto-fills application forms via Playwright agent
- Flask web dashboard + optional Go TUI

## Key files
- `cv.md` — base CV in markdown. Always read this before any evaluation.
- `config/portals.yml` — company career page configs
- `config/profile.example.yml` — template for user profile
- `jobs.db` — SQLite database (see schema in app.py `init_db()`)
- `data/profile.json` — user application profile (gitignored)
- `data/stories.md` — STAR+R interview story bank (gitignored)
- `data/applications.tsv` — application log (gitignored)
- `fetch_jobs.py` — RSS fetcher (reads Tech_Job_RSS_Feeds.xlsx)
- `scan_portals.py` — career portal scraper
- `apply_agent.py` — Playwright form-filling agent
- `generate_pdf.py` — Playwright CV PDF renderer
- `health_check.py` — pipeline integrity checker

## Slash commands (modes/ folder)
- `/jobagent` — show all commands
- `/jobagent eval {url or JD}` — full evaluation pipeline
- `/jobagent pdf {job_id}` — generate tailored CV PDF
- `/jobagent scan` — scan company portals
- `/jobagent apply {job_id}` — launch form filler
- `/jobagent batch` — process batch/pending_urls.txt
- `/jobagent stories` — view/update story bank
- `/jobagent health` — run pipeline health check

## Grading scale
- A = 85–100 (strong match, apply immediately)
- B = 70–84 (good match, worth applying)
- C = 55–69 (partial match, consider tailoring)
- D = 40–54 (weak match, significant gaps)
- F = 0–39 (poor fit)

## Rules
- Always read cv.md before evaluating a job
- Never submit an application without explicit user confirmation
- ATS PDFs must never use tables, columns, or icons — only semantic HTML
- Claude API model: `claude-sonnet-4-6` (current production model)
- All AI scoring uses Claude API, not Ollama
- Dedup by URL before inserting into jobs.db
- Canonical job statuses: new / saved / applied / phone_screen / interview / offer / rejected / archived

## Tech stack
- Python + Flask for web server
- Claude API (`anthropic` SDK) for AI scoring, CV tailoring, form-fill answers
- Playwright for PDF generation and form filling
- SQLite (jobs.db) for storage
- YAML for config files
- Go + Bubble Tea + Lipgloss for TUI
- Vanilla JS for frontend (no framework)
