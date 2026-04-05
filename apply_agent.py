#!/usr/bin/env python3
"""apply_agent.py - Playwright-based application form filler.
Detects ATS platform, fills fields from profile.json, calls Claude API for custom answers.

Usage:
    python apply_agent.py <job_id>
    # Or via Flask: POST /api/apply/<job_id>

Requirements:
    pip install playwright anthropic
    playwright install chromium
"""

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH      = Path(__file__).parent / "jobs.db"
PROFILE_PATH = Path(__file__).parent / "data" / "profile.json"
APP_LOG      = Path(__file__).parent / "data" / "applications.tsv"
OUTPUT_DIR   = Path(__file__).parent / "output"

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL   = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-4-5")
OPENROUTER_BASE    = "https://openrouter.ai/api/v1"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_profile() -> dict:
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    # Fall back to example YAML converted to dict
    return {
        "personal": {
            "first_name": "", "last_name": "", "email": "",
            "phone": "", "linkedin": "", "github": "",
        },
        "work_preferences": {"remote_preference": "remote"},
    }


def detect_ats(url: str) -> str:
    """Detect the ATS platform from the job URL."""
    if "greenhouse.io" in url or "greenhouse" in url:
        return "greenhouse"
    if "ashby" in url:
        return "ashby"
    if "lever.co" in url:
        return "lever"
    if "workday" in url:
        return "workday"
    return "generic"


def claude_custom_answer(question: str, job: dict, profile: dict) -> str:
    """Use the configured AI provider to generate a tailored answer to a free-text field."""
    p = profile.get("personal", {})
    prompt = f"""Write a concise, genuine answer (2-3 sentences max) to this application question.
Be specific, professional, and tailored to the company/role.

Question: {question}
Role: {job.get('title','')}
Company: {job.get('source','')}
Candidate background: {p.get('first_name','')} {p.get('last_name','')} — skills aligned with {job.get('archetype','tech')}.

Answer (no intro, no "Certainly", just the answer):"""

    # Try OpenRouter first if configured
    if OPENROUTER_API_KEY:
        try:
            import requests as req
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://github.com/ekuelkpodar/JobAgents",
                "X-Title":       "JobAgent",
            }
            r = req.post(f"{OPENROUTER_BASE}/chat/completions",
                json={"model": OPENROUTER_MODEL, "max_tokens": 300,
                      "messages": [{"role": "user", "content": prompt}]},
                headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[OpenRouter answer error] {e}")

    # Fallback to Anthropic
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            return msg.content[0].text.strip()
        except Exception as e:
            print(f"[Claude answer error] {e}")

    return f"I am passionate about this {job.get('title', '')} role at {job.get('source', '')}."


def fill_greenhouse(page, profile: dict, job: dict, cv_pdf_path: str | None):
    """Fill a Greenhouse application form."""
    p = profile.get("personal", {})

    def fill(selector: str, value: str):
        try:
            el = page.locator(selector).first
            if el.is_visible():
                el.fill(value)
        except Exception:
            pass

    fill("input[name='first_name'], input[autocomplete='given-name']",   p.get("first_name", ""))
    fill("input[name='last_name'],  input[autocomplete='family-name']",  p.get("last_name", ""))
    fill("input[name='email'],      input[type='email']",                p.get("email", ""))
    fill("input[name='phone'],      input[type='tel']",                  p.get("phone", ""))
    fill("input[name='linkedin_profile_url'], input[placeholder*='LinkedIn']", p.get("linkedin", ""))

    # Upload CV if available
    if cv_pdf_path and Path(cv_pdf_path).exists():
        try:
            upload = page.locator("input[type='file']").first
            if upload.is_visible():
                upload.set_input_files(cv_pdf_path)
                print("[apply] CV uploaded")
        except Exception as e:
            print(f"[apply] CV upload skipped: {e}")

    # Handle free-text fields
    textareas = page.locator("textarea").all()
    for ta in textareas:
        try:
            label_el = ta.evaluate_handle("el => el.closest('div')?.querySelector('label')")
            label    = label_el.as_element().inner_text() if label_el else ""
            if label:
                answer = claude_custom_answer(label, job, profile)
                ta.fill(answer)
                time.sleep(0.3)
        except Exception:
            pass


def fill_ashby(page, profile: dict, job: dict, cv_pdf_path: str | None):
    """Fill an Ashby application form."""
    p = profile.get("personal", {})

    def fill(selector: str, value: str):
        try:
            el = page.locator(selector).first
            if el.is_visible():
                el.fill(value)
        except Exception:
            pass

    fill("input[name='name'], input[placeholder*='Name']",   f"{p.get('first_name','')} {p.get('last_name','')}".strip())
    fill("input[name='email'], input[type='email']",          p.get("email", ""))
    fill("input[name='phone'], input[type='tel']",            p.get("phone", ""))
    fill("input[placeholder*='LinkedIn']",                    p.get("linkedin", ""))
    fill("input[placeholder*='GitHub']",                      p.get("github", ""))

    if cv_pdf_path and Path(cv_pdf_path).exists():
        try:
            page.locator("input[type='file']").first.set_input_files(cv_pdf_path)
        except Exception:
            pass


def fill_lever(page, profile: dict, job: dict, cv_pdf_path: str | None):
    """Fill a Lever application form."""
    p = profile.get("personal", {})

    def fill(selector: str, value: str):
        try:
            el = page.locator(selector).first
            if el.is_visible():
                el.fill(value)
        except Exception:
            pass

    fill("input[name='name']",     f"{p.get('first_name','')} {p.get('last_name','')}".strip())
    fill("input[name='email']",    p.get("email", ""))
    fill("input[name='phone']",    p.get("phone", ""))
    fill("input[name='urls[LinkedIn]']", p.get("linkedin", ""))
    fill("input[name='urls[GitHub]']",   p.get("github", ""))

    if cv_pdf_path and Path(cv_pdf_path).exists():
        try:
            page.locator("input[type='file']").first.set_input_files(cv_pdf_path)
        except Exception:
            pass


def fill_generic(page, profile: dict, job: dict, cv_pdf_path: str | None):
    """Best-effort fill for unknown ATS platforms by label matching."""
    p = profile.get("personal", {})
    field_map = {
        "first name": p.get("first_name", ""),
        "last name":  p.get("last_name", ""),
        "full name":  f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
        "email":      p.get("email", ""),
        "phone":      p.get("phone", ""),
        "linkedin":   p.get("linkedin", ""),
        "github":     p.get("github", ""),
        "portfolio":  p.get("portfolio", ""),
    }
    inputs = page.locator("input[type='text'], input[type='email'], input[type='tel']").all()
    for inp in inputs:
        try:
            label_text = ""
            # Try aria-label
            label_text = inp.get_attribute("aria-label") or ""
            # Try placeholder
            if not label_text:
                label_text = inp.get_attribute("placeholder") or ""
            # Try associated label element
            if not label_text:
                inp_id = inp.get_attribute("id")
                if inp_id:
                    lbl = page.locator(f"label[for='{inp_id}']").first
                    if lbl.is_visible():
                        label_text = lbl.inner_text()
            key = label_text.lower().strip()
            for kw, val in field_map.items():
                if kw in key and val:
                    inp.fill(val)
                    time.sleep(0.1)
                    break
        except Exception:
            pass


def log_application(job: dict, status: str = "filled", cv_version: str = ""):
    """Append to applications.tsv log."""
    APP_LOG.parent.mkdir(exist_ok=True)
    if not APP_LOG.exists():
        APP_LOG.write_text("date\tcompany\trole\turl\tstatus\tcv_version\tnotes\n")
    with open(APP_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()}\t{job.get('source','')}\t{job.get('title','')}\t"
                f"{job.get('url','')}\t{status}\t{cv_version}\t\n")


def apply_to_job(job_id: int, headless: bool = False) -> dict:
    """Main entry point: fill an application for job_id."""
    conn = get_db()
    row  = conn.execute("SELECT * FROM jobs WHERE id=?", [job_id]).fetchone()
    conn.close()
    if not row:
        return {"error": f"Job {job_id} not found"}

    job     = dict(row)
    profile = load_profile()
    url     = job.get("url", "")
    if not url:
        return {"error": "Job has no URL"}

    ats = detect_ats(url)
    print(f"\n[apply] Job: {job['title']}")
    print(f"[apply] URL: {url}")
    print(f"[apply] ATS: {ats}")

    # Find tailored CV PDF if available
    cv_pdf = OUTPUT_DIR / f"cv_{job_id}.pdf"
    cv_pdf_path = str(cv_pdf) if cv_pdf.exists() else None
    if cv_pdf_path:
        print(f"[apply] Using tailored CV: {cv_pdf_path}")
    else:
        print("[apply] No tailored CV found — run /api/generate-cv first for best results")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page    = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Fill based on ATS
        if ats == "greenhouse":
            fill_greenhouse(page, profile, job, cv_pdf_path)
        elif ats == "ashby":
            fill_ashby(page, profile, job, cv_pdf_path)
        elif ats == "lever":
            fill_lever(page, profile, job, cv_pdf_path)
        else:
            fill_generic(page, profile, job, cv_pdf_path)

        print("\n[apply] Form filled. Pausing for review...")
        print("[apply] Press Y to submit, N to cancel, or review and submit manually.")

        # Confirmation prompt
        answer = input("[apply] Submit? (Y/n): ").strip().lower()
        if answer == "y":
            # Try to click submit
            submitted = False
            for selector in ["button[type='submit']", "input[type='submit']", "button:text('Submit')", "button:text('Apply')"]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(2000)
                        submitted = True
                        print("[apply] Submitted successfully!")
                        log_application(job, "submitted", cv_pdf_path or "base")
                        break
                except Exception:
                    pass
            if not submitted:
                print("[apply] Could not find submit button — please submit manually.")
                log_application(job, "manual_review", cv_pdf_path or "base")
        else:
            print("[apply] Submission cancelled. Browser will close.")
            log_application(job, "cancelled", "")

        browser.close()

    return {"ok": True, "ats": ats, "url": url}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python apply_agent.py <job_id>")
        sys.exit(1)
    jid = int(sys.argv[1])
    result = apply_to_job(jid, headless=False)
    print(json.dumps(result, indent=2))
