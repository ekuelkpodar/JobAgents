#!/usr/bin/env python3
"""generate_pdf.py - Render an ATS-safe CV from markdown to PDF using Playwright."""

import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
TEMPLATE   = Path(__file__).parent / "templates" / "cv-template.html"
OUTPUT_DIR.mkdir(exist_ok=True)


def md_to_html_body(md: str) -> str:
    """Convert CV markdown to clean, ATS-safe HTML body content."""
    lines = md.split("\n")
    html_parts = []
    in_ul = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            html_parts.append("")
            continue

        if stripped.startswith("# "):
            if in_ul: html_parts.append("</ul>"); in_ul = False
            text = stripped[2:]
            html_parts.append(f'<h1>{_escape(text)}</h1>')
        elif stripped.startswith("## "):
            if in_ul: html_parts.append("</ul>"); in_ul = False
            text = stripped[3:]
            html_parts.append(f'<h2>{_escape(text)}</h2>')
        elif stripped.startswith("### "):
            if in_ul: html_parts.append("</ul>"); in_ul = False
            text = stripped[4:]
            html_parts.append(f'<h3>{_escape(text)}</h3>')
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                html_parts.append("<ul>")
                in_ul = True
            text = stripped[2:]
            html_parts.append(f"  <li>{_inline(text)}</li>")
        elif stripped.startswith("**") and stripped.endswith("**") and stripped.count("**") == 2:
            if in_ul: html_parts.append("</ul>"); in_ul = False
            text = stripped[2:-2]
            html_parts.append(f'<p class="meta">{_inline(text)}</p>')
        elif stripped.startswith("---"):
            if in_ul: html_parts.append("</ul>"); in_ul = False
            html_parts.append("<hr>")
        else:
            if in_ul: html_parts.append("</ul>"); in_ul = False
            html_parts.append(f"<p>{_inline(stripped)}</p>")

    if in_ul:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    """Handle bold, italic, links inline."""
    text = _escape(text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Links [text](url)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


CV_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CV</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ATS-safe: no tables, no columns, no icons, no floats */
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Space Grotesk', Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.55;
  color: #1a1a2e;
  background: #fff;
  padding: 32px 40px;
  max-width: 800px;
  margin: 0 auto;
}}
h1 {{
  font-size: 22pt;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 4px;
}}
h2 {{
  font-size: 11pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #2d3a8c;
  border-bottom: 1.5px solid #2d3a8c;
  padding-bottom: 3px;
  margin-top: 20px;
  margin-bottom: 10px;
}}
h3 {{
  font-size: 11pt;
  font-weight: 600;
  color: #1a1a2e;
  margin-top: 12px;
  margin-bottom: 2px;
}}
p {{
  margin-bottom: 6px;
  color: #333;
}}
p.meta {{
  font-size: 10pt;
  color: #555;
  margin-bottom: 4px;
}}
ul {{
  margin-left: 18px;
  margin-bottom: 6px;
}}
li {{
  margin-bottom: 3px;
  color: #333;
}}
hr {{
  border: none;
  border-top: 1px solid #ddd;
  margin: 14px 0;
}}
a {{
  color: #2d3a8c;
  text-decoration: none;
}}
strong {{ font-weight: 600; }}
@media print {{
  body {{ padding: 20px 28px; }}
}}
</style>
</head>
<body>
{body}
</body>
</html>"""


def render_cv_pdf(md_content: str, job_id: int) -> Path:
    """Render markdown CV to PDF using Playwright. Returns path to PDF."""
    html_body = md_to_html_body(md_content)
    full_html = CV_HTML_TEMPLATE.format(body=html_body)

    html_path = OUTPUT_DIR / f"cv_{job_id}.html"
    pdf_path  = OUTPUT_DIR / f"cv_{job_id}.pdf"
    html_path.write_text(full_html, encoding="utf-8")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            margin={"top": "25mm", "bottom": "25mm", "left": "20mm", "right": "20mm"},
            print_background=False,
        )
        browser.close()

    return pdf_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python generate_pdf.py <job_id>")
        print("       Reads output/cv_<id>.md and renders output/cv_<id>.pdf")
        sys.exit(1)
    jid = int(sys.argv[1])
    md_path = OUTPUT_DIR / f"cv_{jid}.md"
    if not md_path.exists():
        print(f"No CV found at {md_path}. Generate one first via /api/generate-cv/{jid}")
        sys.exit(1)
    md_text = md_path.read_text(encoding="utf-8")
    out = render_cv_pdf(md_text, jid)
    print(f"PDF saved: {out}")
