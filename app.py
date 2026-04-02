#!/usr/bin/env python3
"""
app.py - JobAgent web dashboard
Serves a dark-mode, filterable job board from jobs.db on http://localhost:5000
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template_string, jsonify, request

DB_PATH = Path(__file__).parent / "jobs.db"

app = Flask(__name__)

# ── DB helper ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def db_exists() -> bool:
    return DB_PATH.exists()


# ── Template ──────────────────────────────────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>JobAgent — Remote Tech Jobs</title>
  <style>
    /* ── Reset & base ── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg:        #0f1117;
      --surface:   #1a1d27;
      --surface2:  #22263a;
      --border:    #2e3350;
      --accent:    #6c63ff;
      --accent2:   #9d97ff;
      --text:      #e2e4f0;
      --muted:     #7a7f9a;
      --green:     #2dd4a0;
      --red:       #f87171;
      --orange:    #fb923c;
      --yellow:    #facc15;
      --cyan:      #22d3ee;
      --pink:      #f472b6;
      --indigo:    #818cf8;
      --radius:    10px;
      --shadow:    0 2px 12px rgba(0,0,0,.45);
    }
    html { font-size: 15px; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh;
    }

    /* ── Layout ── */
    .app-wrap { display: flex; flex-direction: column; min-height: 100vh; }

    /* ── Header ── */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 2px 16px rgba(0,0,0,.5);
    }
    .logo {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: var(--accent2);
      white-space: nowrap;
    }
    .logo span { color: var(--text); }
    .header-stats {
      font-size: .82rem;
      color: var(--muted);
      margin-left: auto;
      white-space: nowrap;
    }
    .header-stats b { color: var(--text); }

    /* ── Main body ── */
    .body-wrap {
      display: flex;
      flex: 1;
      gap: 0;
    }

    /* ── Sidebar ── */
    .sidebar {
      width: 260px;
      min-width: 220px;
      background: var(--surface);
      border-right: 1px solid var(--border);
      padding: 20px 16px;
      display: flex;
      flex-direction: column;
      gap: 20px;
      position: sticky;
      top: 53px;
      height: calc(100vh - 53px);
      overflow-y: auto;
    }
    .sidebar::-webkit-scrollbar { width: 4px; }
    .sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

    .filter-section label.section-label {
      display: block;
      font-size: .72rem;
      font-weight: 600;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }

    /* Search */
    .search-wrap { position: relative; }
    .search-wrap input {
      width: 100%;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      color: var(--text);
      font-size: .88rem;
      padding: 8px 10px 8px 32px;
      outline: none;
      transition: border-color .15s;
    }
    .search-wrap input:focus { border-color: var(--accent); }
    .search-wrap::before {
      content: "🔍";
      font-size: .78rem;
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      pointer-events: none;
    }

    /* Date range */
    .btn-group { display: flex; flex-direction: column; gap: 5px; }
    .btn-filter {
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 7px;
      color: var(--muted);
      cursor: pointer;
      font-size: .82rem;
      padding: 6px 10px;
      text-align: left;
      transition: all .15s;
    }
    .btn-filter:hover { border-color: var(--accent); color: var(--text); }
    .btn-filter.active {
      background: rgba(108,99,255,.18);
      border-color: var(--accent);
      color: var(--accent2);
    }

    /* Sort */
    select.filter-select {
      width: 100%;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      color: var(--text);
      font-size: .82rem;
      padding: 7px 10px;
      outline: none;
      cursor: pointer;
    }
    select.filter-select:focus { border-color: var(--accent); }

    /* Checkbox lists */
    .check-list {
      display: flex;
      flex-direction: column;
      gap: 5px;
      max-height: 200px;
      overflow-y: auto;
      padding-right: 2px;
    }
    .check-list::-webkit-scrollbar { width: 3px; }
    .check-list::-webkit-scrollbar-thumb { background: var(--border); }
    .check-item {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: .82rem;
      color: var(--muted);
      padding: 2px 4px;
      border-radius: 5px;
      transition: color .12s;
      user-select: none;
    }
    .check-item:hover { color: var(--text); }
    .check-item input[type="checkbox"] {
      accent-color: var(--accent);
      width: 13px;
      height: 13px;
      cursor: pointer;
      flex-shrink: 0;
    }
    .check-item .badge-mini {
      margin-left: auto;
      font-size: .68rem;
      background: var(--surface2);
      border-radius: 10px;
      padding: 1px 6px;
      color: var(--muted);
    }

    /* Clear btn */
    .btn-clear {
      background: rgba(248,113,113,.1);
      border: 1px solid rgba(248,113,113,.25);
      border-radius: var(--radius);
      color: var(--red);
      cursor: pointer;
      font-size: .8rem;
      font-weight: 500;
      padding: 7px 12px;
      width: 100%;
      transition: all .15s;
    }
    .btn-clear:hover { background: rgba(248,113,113,.2); }

    /* ── Content area ── */
    .content {
      flex: 1;
      padding: 20px 24px;
      overflow: hidden;
    }

    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      gap: 12px;
      flex-wrap: wrap;
    }
    .result-count {
      font-size: .85rem;
      color: var(--muted);
    }
    .result-count b { color: var(--text); }

    /* ── Job grid ── */
    .job-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 14px;
    }

    .job-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      transition: border-color .15s, transform .1s;
      position: relative;
    }
    .job-card:hover {
      border-color: var(--accent);
      transform: translateY(-1px);
      box-shadow: var(--shadow);
    }

    .job-title a {
      font-size: .96rem;
      font-weight: 600;
      color: var(--text);
      text-decoration: none;
      line-height: 1.35;
    }
    .job-title a:hover { color: var(--accent2); }

    .job-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }

    .badge {
      font-size: .68rem;
      font-weight: 600;
      letter-spacing: .04em;
      padding: 2px 8px;
      border-radius: 20px;
      white-space: nowrap;
    }
    .badge-source {
      background: rgba(108,99,255,.15);
      color: var(--accent2);
      border: 1px solid rgba(108,99,255,.3);
    }
    .badge-feed {
      background: rgba(34,211,238,.1);
      color: var(--cyan);
      border: 1px solid rgba(34,211,238,.2);
    }

    /* Category colors */
    .cat-engineering  { background: rgba(45,212,160,.12); color: var(--green);  border: 1px solid rgba(45,212,160,.25); }
    .cat-ai-ml        { background: rgba(248,113,113,.12); color: var(--red);   border: 1px solid rgba(248,113,113,.25); }
    .cat-devops       { background: rgba(251,146,60,.12);  color: var(--orange); border: 1px solid rgba(251,146,60,.25); }
    .cat-data-science { background: rgba(250,204,21,.12);  color: var(--yellow); border: 1px solid rgba(250,204,21,.25); }
    .cat-security     { background: rgba(248,113,113,.15); color: #fca5a5;      border: 1px solid rgba(248,113,113,.3); }
    .cat-product      { background: rgba(244,114,182,.12); color: var(--pink);  border: 1px solid rgba(244,114,182,.25); }
    .cat-design       { background: rgba(129,140,248,.12); color: var(--indigo); border: 1px solid rgba(129,140,248,.25); }
    .cat-marketing    { background: rgba(250,204,21,.1);   color: #fde68a;      border: 1px solid rgba(250,204,21,.2); }
    .cat-web3         { background: rgba(45,212,160,.1);   color: #6ee7b7;      border: 1px solid rgba(45,212,160,.2); }
    .cat-general      { background: rgba(122,127,154,.12); color: var(--muted); border: 1px solid rgba(122,127,154,.25); }

    .job-date {
      font-size: .75rem;
      color: var(--muted);
      margin-left: auto;
    }

    .job-desc {
      font-size: .8rem;
      color: var(--muted);
      line-height: 1.55;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
    }

    /* Load more */
    .load-more-wrap {
      text-align: center;
      margin-top: 24px;
    }
    .btn-load-more {
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      color: var(--text);
      cursor: pointer;
      font-size: .88rem;
      font-weight: 500;
      padding: 10px 28px;
      transition: all .15s;
    }
    .btn-load-more:hover { border-color: var(--accent); color: var(--accent2); }

    /* Empty state */
    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: var(--muted);
    }
    .empty-state h2 { font-size: 1.2rem; margin-bottom: 8px; color: var(--text); }

    /* ── Responsive ── */
    @media (max-width: 768px) {
      .sidebar { display: none; }
      .content { padding: 14px; }
      .job-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<div class="app-wrap">

  <!-- Header -->
  <header>
    <div class="logo">Job<span>Agent</span></div>
    <div class="header-stats">
      <b id="hdr-total">{{ total_jobs }}</b> jobs &nbsp;·&nbsp;
      last updated <b>{{ last_updated }}</b>
    </div>
  </header>

  <div class="body-wrap">

    <!-- Sidebar -->
    <aside class="sidebar">

      <!-- Search -->
      <div class="filter-section">
        <label class="section-label">Search</label>
        <div class="search-wrap">
          <input type="text" id="search-input" placeholder="Title, company, keywords…" autocomplete="off" />
        </div>
      </div>

      <!-- Date range -->
      <div class="filter-section">
        <label class="section-label">Date Range</label>
        <div class="btn-group">
          <button class="btn-filter" data-range="today">Today</button>
          <button class="btn-filter active" data-range="7">Last 7 days</button>
          <button class="btn-filter" data-range="30">Last 30 days</button>
          <button class="btn-filter" data-range="all">All time</button>
        </div>
      </div>

      <!-- Sort -->
      <div class="filter-section">
        <label class="section-label">Sort</label>
        <select id="sort-select" class="filter-select">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="source">Source A–Z</option>
        </select>
      </div>

      <!-- Category -->
      <div class="filter-section">
        <label class="section-label">Category</label>
        <div class="check-list" id="cat-list">
          {% for cat, cnt in categories %}
          <label class="check-item">
            <input type="checkbox" class="cat-check" value="{{ cat }}" checked />
            {{ cat }}
            <span class="badge-mini">{{ cnt }}</span>
          </label>
          {% endfor %}
        </div>
      </div>

      <!-- Source -->
      <div class="filter-section">
        <label class="section-label">Source</label>
        <div class="check-list" id="src-list">
          {% for src, cnt in sources %}
          <label class="check-item">
            <input type="checkbox" class="src-check" value="{{ src }}" checked />
            {{ src }}
            <span class="badge-mini">{{ cnt }}</span>
          </label>
          {% endfor %}
        </div>
      </div>

      <!-- Clear -->
      <button class="btn-clear" id="btn-clear">✕ Clear all filters</button>

    </aside>

    <!-- Main content -->
    <main class="content">
      <div class="toolbar">
        <div class="result-count" id="result-count">
          Showing <b id="count-visible">0</b> of <b id="count-total">0</b> jobs
        </div>
      </div>

      <div class="job-grid" id="job-grid"></div>

      <div class="load-more-wrap" id="load-more-wrap" style="display:none">
        <button class="btn-load-more" id="btn-load-more">Load more jobs</button>
      </div>

      <div class="empty-state" id="empty-state" style="display:none">
        <h2>No jobs found</h2>
        <p>Try adjusting your search or filters.</p>
      </div>
    </main>
  </div>
</div>

<script>
(function () {
  "use strict";

  // ── All jobs injected from server ────────────────────────────────────────
  const ALL_JOBS = {{ jobs_json | safe }};
  const PAGE_SIZE = 200;

  // ── State ────────────────────────────────────────────────────────────────
  let filtered   = [];
  let displayed  = 0;
  const state = {
    query:    "",
    range:    "7",
    sort:     "newest",
    cats:     new Set(),
    sources:  new Set(),
  };

  // ── Init category/source sets from checked boxes ──────────────────────────
  function initSets() {
    document.querySelectorAll(".cat-check").forEach(cb => {
      if (cb.checked) state.cats.add(cb.value);
    });
    document.querySelectorAll(".src-check").forEach(cb => {
      if (cb.checked) state.sources.add(cb.value);
    });
  }

  // ── Relative time ─────────────────────────────────────────────────────────
  function relativeTime(iso) {
    if (!iso) return "Unknown date";
    const d   = new Date(iso);
    if (isNaN(d)) return iso.slice(0, 10);
    const now = Date.now();
    const sec = Math.floor((now - d) / 1000);
    if (sec < 60)    return "just now";
    if (sec < 3600)  return `${Math.floor(sec/60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec/3600)}h ago`;
    const days = Math.floor(sec/86400);
    if (days < 30)   return `${days}d ago`;
    if (days < 365)  return `${Math.floor(days/30)}mo ago`;
    return `${Math.floor(days/365)}y ago`;
  }

  // ── Category CSS class ────────────────────────────────────────────────────
  function catClass(cat) {
    const map = {
      "Engineering":  "cat-engineering",
      "AI/ML":        "cat-ai-ml",
      "DevOps":       "cat-devops",
      "Data Science": "cat-data-science",
      "Security":     "cat-security",
      "Product":      "cat-product",
      "Design":       "cat-design",
      "Marketing":    "cat-marketing",
      "Web3":         "cat-web3",
      "General":      "cat-general",
    };
    return map[cat] || "cat-general";
  }

  // ── Escape HTML ───────────────────────────────────────────────────────────
  function esc(s) {
    return String(s || "")
      .replace(/&/g,"&amp;").replace(/</g,"&lt;")
      .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  // ── Build a card ──────────────────────────────────────────────────────────
  function buildCard(job) {
    const desc = (job.description || "").slice(0, 200);
    return `
      <div class="job-card">
        <div class="job-title">
          <a href="${esc(job.url)}" target="_blank" rel="noopener noreferrer">${esc(job.title)}</a>
        </div>
        <div class="job-meta">
          <span class="badge badge-source">${esc(job.source)}</span>
          <span class="badge badge-feed">${esc(job.feed_name)}</span>
          <span class="badge ${catClass(job.category)}">${esc(job.category)}</span>
          <span class="job-date">${relativeTime(job.published_date)}</span>
        </div>
        ${desc ? `<div class="job-desc">${esc(desc)}</div>` : ""}
      </div>`;
  }

  // ── Date cutoff helpers ───────────────────────────────────────────────────
  function cutoff(range) {
    if (range === "all") return null;
    const now = Date.now();
    if (range === "today") return now - 86400000;
    return now - parseInt(range, 10) * 86400000;
  }

  // ── Filter & sort ─────────────────────────────────────────────────────────
  function applyFilters() {
    const q   = state.query.toLowerCase();
    const cut = cutoff(state.range);

    filtered = ALL_JOBS.filter(job => {
      if (!state.cats.has(job.category))  return false;
      if (!state.sources.has(job.source)) return false;
      if (cut && job.published_date) {
        const d = new Date(job.published_date);
        if (!isNaN(d) && d.getTime() < cut) return false;
      }
      if (q) {
        const haystack = `${job.title} ${job.description} ${job.source} ${job.feed_name}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });

    // Sort
    filtered.sort((a, b) => {
      if (state.sort === "newest") {
        return new Date(b.published_date) - new Date(a.published_date);
      }
      if (state.sort === "oldest") {
        return new Date(a.published_date) - new Date(b.published_date);
      }
      // source A–Z
      return (a.source || "").localeCompare(b.source || "");
    });

    displayed = 0;
    document.getElementById("job-grid").innerHTML = "";
    renderMore();
    document.getElementById("count-total").textContent = filtered.length.toLocaleString();
    document.getElementById("hdr-total").textContent   = ALL_JOBS.length.toLocaleString();
  }

  // ── Render next page ──────────────────────────────────────────────────────
  function renderMore() {
    const grid  = document.getElementById("job-grid");
    const chunk = filtered.slice(displayed, displayed + PAGE_SIZE);
    chunk.forEach(job => {
      const el = document.createElement("div");
      el.innerHTML = buildCard(job);
      grid.appendChild(el.firstElementChild);
    });
    displayed += chunk.length;

    document.getElementById("count-visible").textContent = displayed.toLocaleString();

    const lmw = document.getElementById("load-more-wrap");
    lmw.style.display = (displayed < filtered.length) ? "block" : "none";

    const es = document.getElementById("empty-state");
    es.style.display = (filtered.length === 0) ? "block" : "none";
  }

  // ── Event wiring ──────────────────────────────────────────────────────────
  // Search (debounced)
  let searchTimer;
  document.getElementById("search-input").addEventListener("input", e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = e.target.value.trim();
      applyFilters();
    }, 200);
  });

  // Date range buttons
  document.querySelectorAll(".btn-filter[data-range]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-filter[data-range]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.range = btn.dataset.range;
      applyFilters();
    });
  });

  // Sort
  document.getElementById("sort-select").addEventListener("change", e => {
    state.sort = e.target.value;
    applyFilters();
  });

  // Category checkboxes
  document.getElementById("cat-list").addEventListener("change", e => {
    if (e.target.classList.contains("cat-check")) {
      e.target.checked ? state.cats.add(e.target.value) : state.cats.delete(e.target.value);
      applyFilters();
    }
  });

  // Source checkboxes
  document.getElementById("src-list").addEventListener("change", e => {
    if (e.target.classList.contains("src-check")) {
      e.target.checked ? state.sources.add(e.target.value) : state.sources.delete(e.target.value);
      applyFilters();
    }
  });

  // Load more
  document.getElementById("btn-load-more").addEventListener("click", renderMore);

  // Clear all
  document.getElementById("btn-clear").addEventListener("click", () => {
    document.getElementById("search-input").value = "";
    state.query = "";
    state.range = "7";
    state.sort  = "newest";
    document.querySelectorAll(".btn-filter[data-range]").forEach(b =>
      b.classList.toggle("active", b.dataset.range === "7")
    );
    document.getElementById("sort-select").value = "newest";
    document.querySelectorAll(".cat-check, .src-check").forEach(cb => { cb.checked = true; });
    initSets();
    applyFilters();
  });

  // ── Boot ──────────────────────────────────────────────────────────────────
  initSets();
  applyFilters();
})();
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if not db_exists():
        return (
            "<h2 style='font-family:sans-serif;color:#ccc;margin:40px'>No database found."
            " Run <code>python fetch_jobs.py</code> first.</h2>",
            503,
        )

    conn = get_db()

    # All jobs
    rows = conn.execute(
        "SELECT title, url, published_date, source, feed_name, category, description "
        "FROM jobs ORDER BY published_date DESC"
    ).fetchall()

    # Stats for sidebar
    categories = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM jobs GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    sources = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM jobs GROUP BY source ORDER BY cnt DESC"
    ).fetchall()

    # Last updated
    last_row = conn.execute("SELECT MAX(fetched_at) FROM jobs").fetchone()
    conn.close()

    last_updated = "never"
    if last_row and last_row[0]:
        try:
            dt = datetime.fromisoformat(last_row[0])
            last_updated = dt.strftime("%b %d, %Y %H:%M UTC")
        except Exception:
            last_updated = str(last_row[0])[:16]

    jobs_list = [dict(r) for r in rows]

    return render_template_string(
        HTML,
        jobs_json=json.dumps(jobs_list, default=str),
        total_jobs=len(jobs_list),
        last_updated=last_updated,
        categories=categories,
        sources=sources,
    )


if __name__ == "__main__":
    print("\n  JobAgent Web Dashboard")
    print("  Open http://localhost:5000\n")
    app.run(debug=False, port=5000)
