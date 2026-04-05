# JobAgent — AI Job Board + Application Autopilot

A fully local job aggregator that pulls listings from 100 tech job feeds, matches them to your resume with AI, and lets you fill out a single **Application Profile** that browser agents can use to auto-apply on your behalf.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![Flask](https://img.shields.io/badge/Flask-3.1-green) ![SQLite](https://img.shields.io/badge/Database-SQLite-orange) ![Ollama](https://img.shields.io/badge/AI-Ollama%20%2F%20LLaMA3-purple) ![Windows](https://img.shields.io/badge/Windows-compatible-0078D4?logo=windows)

---

## Dashboard

![JobAgent Dashboard](Dashboard.png)

---

## Features

| Feature | Detail |
|---|---|
| RSS Aggregator | 100 feeds across Engineering, AI/ML, DevOps, Data, Security, Design, Web3, and more |
| Local SQLite | All jobs stored locally — no API keys, no external services |
| Dark-mode Dashboard | Live search, category/source filters, date range, sort, pagination |
| AI Resume Match | Upload your resume → LLaMA3 scores every job for fit |
| Saved Jobs | Bookmark roles and review them in a dedicated tab |
| **Application Profile** | Form that captures everything needed to auto-apply — exports to Word, PDF, or JSON |
| **Browser Agent Ready** | JSON export feeds directly into AI browser agents (e.g. Playwright, Skyvern, LaVague) |
| Resilient Fetcher | Skips failed feeds and logs errors; never crashes mid-run |

---

## Application Profile Form

`http://localhost:5000/profile`

Fill this out once and your browser agent handles the rest. The form covers every field a job application typically asks for beyond your resume and cover letter:

- **Personal Info** — name, email, phone, location, LinkedIn, GitHub, portfolio
- **Work Eligibility** — visa status, sponsorship needs, remote/hybrid preference, start date
- **Work History** — repeating blocks for each role (title, company, dates, responsibilities, manager)
- **Education** — degrees, majors, GPA, graduation dates
- **Skills & Certifications** — tech stack, tools, languages, licenses
- **Screening Answers** — pre-written responses to "Why this company?", strengths, 5-year plan, etc.
- **Portfolio / Work Samples** — project links with descriptions
- **References** — names, titles, contact info
- **Compensation** — desired salary range, currency, notes for negotiation
- **EEO & Compliance** — optional diversity fields, background check consent

### Export formats

| Format | Use case |
|---|---|
| `.docx` | Human-readable copy, works out of the box |
| `.pdf` | Requires `pip install docx2pdf` |
| `.json` | Machine-readable flat file — feed directly to a browser agent |

---

## Quickstart

> **Windows users:** fully supported on Windows 10/11. Use the same commands below in PowerShell, Command Prompt, or Git Bash.

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Fetch jobs (~5–10 min on first run)
```bash
python fetch_jobs.py
```
Reads all feeds from `Tech_Job_RSS_Feeds.xlsx`, stores results in `jobs.db`. Feed errors are logged to `fetch_errors.log` and skipped automatically.

### 3. Start the server
```bash
python app.py
```

| URL | Page |
|---|---|
| http://localhost:5000 | Job board dashboard |
| http://localhost:5000/profile | Application profile form |

---

## Project Structure

```
JobAgent/
├── fetch_jobs.py              # RSS fetcher — reads XLSX, populates jobs.db
├── app.py                     # Flask server — dashboard + AI match + profile form
├── requirements.txt           # Python dependencies
├── Tech_Job_RSS_Feeds.xlsx    # 100 RSS feed URLs with source/category metadata
└── README.md
```

> `jobs.db` and `fetch_errors.log` are generated at runtime.

---

## Dependencies

```
feedparser     — RSS/Atom feed parsing
flask          — Web server
openpyxl       — Read .xlsx feed list
requests       — HTTP fetching with timeout support
pypdf          — PDF resume parsing
python-docx    — Profile export to .docx
docx2pdf       — (optional) Profile export to PDF
```

---

## System Design

```mermaid
flowchart TD
    A([Tech_Job_RSS_Feeds.xlsx\n100 feeds · source · category]) --> B[fetch_jobs.py]

    B --> C{For each feed}
    C -->|requests + timeout| D[RSS/Atom Feed URL]
    D -->|feedparser| E[Parse entries\ntitle · url · date · description]
    E --> F[(jobs.db\nSQLite)]
    C -->|on error| G[fetch_errors.log]

    F --> H[app.py\nFlask server]

    H --> I[GET /\nJob Board Dashboard]
    H --> I2[GET /profile\nApplication Profile Form]

    I --> J[Browser\nhttp://localhost:5000]

    subgraph Dashboard [Dark-mode Dashboard — vanilla JS]
        J --> K[Sidebar Filters\nsearch · category · source · date · sort]
        K --> L[Live Filter Engine\nclient-side · no reload]
        L --> M[Job Cards Grid\ntitle · badges · date · snippet]
        M --> N[Save Job ★]
    end

    I --> O[POST /api/match\nResume Upload]
    O -->|text extraction| P[pypdf / docx parser]
    P -->|prompt| Q[Ollama LLaMA3\nlocalhost:11434]
    Q -->|match score + reasoning| R[Ranked Job Results]

    I2 --> S[Profile Form\n10 sections · repeating blocks]
    S -->|POST /api/profile/save| T{Export Format}
    T -->|docx| U[Word Document\nDownload]
    T -->|pdf| V[PDF\nDownload]
    T -->|json| W[JSON File\nBrowser Agent Input]

    W --> X([AI Browser Agent\nPlaywright · Skyvern · LaVague])
    X --> Y([Job Application Sites\nLinkedIn · Workday · Greenhouse])

    style A fill:#1a1d27,color:#e2e4f0,stroke:#2e3350
    style F fill:#1a1d27,color:#e2e4f0,stroke:#6c63ff
    style Dashboard fill:#0f1117,color:#e2e4f0,stroke:#2e3350
    style G fill:#1a1d27,color:#f87171,stroke:#f87171
    style W fill:#1a1d27,color:#00d4aa,stroke:#00d4aa
    style X fill:#1a1d27,color:#00d4aa,stroke:#00d4aa
    style Y fill:#1a1d27,color:#fbbf24,stroke:#fbbf24
```

---

## Notes

- ~55 of 100 feeds are currently active; the rest return 404/403/410 (dead or blocked URLs)
- Indeed and Upwork RSS feeds are blocked; Dice RSS endpoints are defunct
- Run `fetch_jobs.py` on a schedule (e.g. daily cron) to keep jobs fresh
- AI matching requires [Ollama](https://ollama.com) running locally with the `llama3.2` model pulled
