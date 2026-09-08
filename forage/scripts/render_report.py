"""Render a Markdown report to a print-quality PDF alongside it.

The .md stays the source of truth -- it is what the agent writes, what diffs
cleanly, and what you edit. The .pdf is a derived artifact for circulating to
researchers and PIs, regenerated whenever the .md changes.

Backends, in preference order:
  1. headless Chrome  -- real CSS, correct tables, controlled page breaks
  2. cupsfilter       -- built into macOS, no install, but crude layout

Usage
-----
  python3 scripts/render_report.py output/some_report.md
  python3 scripts/render_report.py --all           # every .md in output/
  python3 scripts/render_report.py --all --force   # ignore mtime check
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

CHROME_CANDIDATES = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    # Linux
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
    # Windows
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]

CSS = """
@page { size: Letter; margin: 0.7in 0.65in 0.75in 0.65in; }

:root {
  --ink:        #1a1a1a;
  --muted:      #5b6472;
  --rule:       #d8dde3;
  --accent:     #1f4e79;
  --warn-bg:    #fff8e6;
  --warn-edge:  #d9a441;
  --code-bg:    #f4f6f8;
  --head-bg:    #eef2f6;
}

* { box-sizing: border-box; }

body {
  font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 10.2pt;
  line-height: 1.5;
  color: var(--ink);
  margin: 0;
  -webkit-font-smoothing: antialiased;
}

h1 {
  font-size: 19pt; line-height: 1.22; margin: 0 0 2pt;
  color: var(--accent); letter-spacing: -0.01em;
}
h2 {
  font-size: 13pt; margin: 20pt 0 7pt; padding-bottom: 3pt;
  border-bottom: 1.5px solid var(--accent); color: var(--accent);
  break-after: avoid-page;
}
h3 {
  font-size: 11pt; margin: 14pt 0 4pt; color: var(--ink);
  break-after: avoid-page;
}
h4 { font-size: 10pt; margin: 10pt 0 3pt; color: var(--muted); }

p { margin: 0 0 7pt; orphans: 3; widows: 3; }
ul, ol { margin: 0 0 8pt; padding-left: 17pt; }
li { margin-bottom: 2.5pt; }
li > ul, li > ol { margin-top: 2.5pt; }

strong { font-weight: 650; }
a { color: var(--accent); text-decoration: none; }

hr { border: 0; border-top: 1px solid var(--rule); margin: 16pt 0; }

/* Tables: the reports lean on these heavily, so they must not fracture. */
table {
  border-collapse: collapse; width: 100%;
  margin: 8pt 0 12pt; font-size: 8.9pt;
  break-inside: avoid-page;
}
th {
  background: var(--head-bg); text-align: left;
  font-weight: 650; font-size: 8.4pt;
  text-transform: uppercase; letter-spacing: 0.04em;
  padding: 5pt 7pt; border-bottom: 1.5px solid var(--accent);
}
td {
  padding: 4.5pt 7pt; border-bottom: 1px solid var(--rule);
  vertical-align: top;
}
tr:last-child td { border-bottom: none; }

code {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.86em; background: var(--code-bg);
  padding: 1pt 3pt; border-radius: 2.5px;
  word-break: break-all;
}
pre {
  background: var(--code-bg); border: 1px solid var(--rule);
  border-radius: 4px; padding: 8pt 10pt; overflow-x: auto;
  font-size: 8.6pt; line-height: 1.4; break-inside: avoid-page;
}
pre code { background: none; padding: 0; word-break: normal; }

/* The "Goal as understood" restatement and similar callouts. */
blockquote {
  margin: 8pt 0; padding: 7pt 12pt;
  background: var(--code-bg);
  border-left: 3px solid var(--accent);
  color: var(--ink); font-style: italic;
  break-inside: avoid-page;
}
blockquote p:last-child { margin-bottom: 0; }

/* Paragraphs opening with a warning sign read as caveats -- make them look it. */
p.callout {
  background: var(--warn-bg); border-left: 3px solid var(--warn-edge);
  padding: 7pt 11pt; margin: 8pt 0; break-inside: avoid-page;
}

.report-meta {
  color: var(--muted); font-size: 9pt;
  margin: 0 0 12pt; padding-bottom: 9pt;
  border-bottom: 2px solid var(--accent);
}
.footer-note {
  margin-top: 18pt; padding-top: 7pt; border-top: 1px solid var(--rule);
  color: var(--muted); font-size: 8.4pt; font-style: italic;
}
em { color: inherit; }
"""

HTML_SHELL = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head>
<body>
{body}
</body></html>
"""


def find_chrome() -> Optional[str]:
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser", "chrome", "msedge", "brave"):
        found = shutil.which(name)
        if found:
            return found
    return None


FIELD_LINE = re.compile(r"^\*\*[^*\n]+:\*\*")


def _preserve_field_breaks(md_text: str) -> str:
    """Keep each '**Label:** value' line on its own line in the PDF.

    No nl2br: the .md is hard-wrapped for readable diffs, and turning every
    source newline into a <br> would break prose at arbitrary columns.

    The break has to be forced on the line BEFORE each field line, not after
    it. A field line whose value wraps ("**Fit:** ...long text") continues on
    an unmarked line, and without this the following "**Project:**" would be
    swallowed into that continuation.
    """
    lines = md_text.split("\n")
    for i in range(len(lines) - 1):
        if not FIELD_LINE.match(lines[i + 1]):
            continue
        current = lines[i]
        if current.strip() and not current.endswith("  "):
            lines[i] = current + "  "
    return "\n".join(lines)


def md_to_html(md_text: str, title: str) -> str:
    md_text = _preserve_field_breaks(md_text)

    html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
        output_format="html5",
    )
    # Style the caveat paragraphs and the trailing provenance note.
    html = re.sub(r"<p>(\s*(?:&#9888;|⚠)[^<]*)", r'<p class="callout">\1', html)
    html = re.sub(
        r"<p><em>(Read-only throughout|Generated by the Globus)",
        r'<p class="footer-note"><em>\1',
        html,
    )
    return HTML_SHELL.format(title=title, css=CSS, body=html)


def _chrome_attempt(chrome: str, headless_flag: str, html_path: Path,
                    pdf_path: Path, timeout: int) -> bool:
    profile = tempfile.mkdtemp(prefix="globus-agent-chrome-")
    argv = [
        chrome, headless_flag,
        "--disable-gpu", "--no-sandbox", "--no-first-run",
        "--disable-extensions", "--disable-background-networking",
        "--user-data-dir=" + profile,
        "--no-pdf-header-footer",
        "--print-to-pdf=" + str(pdf_path),
        html_path.as_uri(),
    ]
    # NOT capture_output: Chrome's helpers inherit the pipes, so after a
    # timeout kill communicate() blocks forever waiting for EOF.
    #
    # And don't just wait for exit -- Chrome writes the PDF, then lingers,
    # burning the whole timeout on every render. Poll for the file to appear
    # and stop growing, then shut it down.
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError:
        shutil.rmtree(profile, ignore_errors=True)
        return False

    deadline = time.time() + timeout
    last_size, stable = -1, 0
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if pdf_path.exists():
                size = pdf_path.stat().st_size
                if size > 1000 and size == last_size:
                    stable += 1
                    if stable >= 2:  # ~0.5s unchanged: the write has landed
                        break
                else:
                    stable = 0
                last_size = size
            time.sleep(0.25)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    # Chrome writes a 0-byte file on failure; treat that as no output at all.
    if pdf_path.exists() and pdf_path.stat().st_size <= 1000:
        pdf_path.unlink()
    return pdf_path.exists()


def html_to_pdf_chrome(chrome: str, html_path: Path, pdf_path: Path) -> bool:
    """One attempt per headless dialect, never both timeouts on the same flag."""
    for flag in ("--headless=new", "--headless"):
        if _chrome_attempt(chrome, flag, html_path, pdf_path, timeout=40):
            return True
    return False


def html_to_pdf_cupsfilter(html_path: Path, pdf_path: Path) -> bool:
    """macOS fallback. No CSS support worth the name, but always present."""
    try:
        with pdf_path.open("wb") as out:
            res = subprocess.run(["cupsfilter", "-t", "report", str(html_path)],
                                 stdout=out, stderr=subprocess.PIPE, timeout=120)
        return res.returncode == 0 and pdf_path.stat().st_size > 1000
    except (subprocess.SubprocessError, OSError):
        return False


def render(md_path: Path, keep_html: bool = False) -> Optional[Path]:
    md_path = md_path.resolve()  # as_uri() below requires an absolute path
    md_text = md_path.read_text(encoding="utf-8")
    m = re.search(r"^#\s+(.+)$", md_text, re.M)
    title = m.group(1).strip() if m else md_path.stem

    html_path = md_path.with_suffix(".html")
    html_path.write_text(md_to_html(md_text, title), encoding="utf-8")
    pdf_path = md_path.with_suffix(".pdf")
    if pdf_path.exists():
        pdf_path.unlink()

    chrome = find_chrome()
    ok = html_to_pdf_chrome(chrome, html_path, pdf_path) if chrome else False
    backend = "chrome"
    if not ok:
        ok = html_to_pdf_cupsfilter(html_path, pdf_path)
        backend = "cupsfilter"

    if not keep_html:
        html_path.unlink(missing_ok=True)

    if not ok:
        print("  FAILED: {}".format(md_path.name))
        return None
    print("  {} -> {}  ({:.0f} KB, {})".format(
        md_path.name, pdf_path.name, pdf_path.stat().st_size / 1024, backend))
    return pdf_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="markdown files to render")
    ap.add_argument("--all", action="store_true", help="render every .md in output/")
    ap.add_argument("--force", action="store_true",
                    help="re-render even when the pdf is newer than the md")
    ap.add_argument("--keep-html", action="store_true",
                    help="leave the intermediate .html for styling work")
    args = ap.parse_args()

    targets: List[Path] = [Path(p) for p in args.paths]
    if args.all:
        targets = sorted(OUTPUT_DIR.glob("*.md"))
    if not targets:
        sys.exit("nothing to render (pass a .md path or --all)")

    print("rendering {} report(s)".format(len(targets)), flush=True)
    made = 0
    for md_path in targets:
        if not md_path.exists():
            print("  missing: {}".format(md_path))
            continue
        pdf = md_path.with_suffix(".pdf")
        if pdf.exists() and not args.force \
                and pdf.stat().st_mtime >= md_path.stat().st_mtime:
            print("  {} -> up to date".format(md_path.name))
            continue
        if render(md_path, args.keep_html):
            made += 1
    print("done: {} pdf(s) written".format(made))


if __name__ == "__main__":
    main()
