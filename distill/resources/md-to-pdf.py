#!/usr/bin/env python3
"""
Render a research-report Markdown file to a styled PDF.

Usage:
    ./.venv/bin/python resources/md-to-pdf.py output/YYYY-MM-DD_topic-slug.md

Writes the PDF alongside the source (same name, .pdf extension).

Pipeline: Markdown -> styled HTML -> headless Chrome print-to-PDF.
Requires: the `markdown` package (see requirements.txt) and a Chrome-family
browser -- Chrome, Chromium, Edge or Brave, found by path or on PATH.

Interpreter note: `markdown` lives in the project venv, but this script is
often run as a bare `python3 resources/md-to-pdf.py`, where PATH may resolve to
a conda or system interpreter that lacks it. On ImportError the script re-execs
itself under the first interpreter that has it -- the venv, then the system
one -- so either invocation works.
"""
import html
import os
import shutil
import subprocess
import sys
import tempfile

SYSTEM_PYTHON = "/usr/bin/python3"
# The project venv, two levels up from resources/md-to-pdf.py.
VENV_PYTHON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".venv", "bin", "python",
)

try:
    import markdown
except ImportError:
    # `markdown` lives in the project venv, but this script is routinely run as
    # a bare `python3 resources/md-to-pdf.py`, where PATH may resolve to a
    # conda or system interpreter that lacks it. Re-exec under the first
    # interpreter that actually has it: the venv, then the system one (which is
    # where older setups installed it with `pip install --user`).
    _already_tried = os.environ.get("MD2PDF_REEXEC") == "1"
    if not _already_tried:
        for _candidate in (VENV_PYTHON, SYSTEM_PYTHON):
            if not os.path.exists(_candidate):
                continue
            if os.path.realpath(_candidate) == os.path.realpath(sys.executable):
                continue  # already here, and the import still failed
            _probe = subprocess.run(
                [_candidate, "-c", "import markdown"], capture_output=True
            )
            if _probe.returncode != 0:
                continue
            env = dict(os.environ, MD2PDF_REEXEC="1")
            print(f"note: re-executing under {_candidate} (markdown not in {sys.executable})",
                  file=sys.stderr)
            os.execve(_candidate, [_candidate, os.path.abspath(__file__), *sys.argv[1:]], env)
    sys.exit(
        "error: missing dependency `markdown`.\n"
        f"  tried: {sys.executable}\n"
        "  fix:   python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt\n"
        "  then:  ./.venv/bin/python resources/md-to-pdf.py <file>.md"
    )

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
@page { size: Letter; margin: 0.85in 0.8in; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.5; color: #1a1a1a; margin: 0;
}
h1 { font-size: 19pt; line-height: 1.25; margin: 0 0 .5em; color: #111;
     border-bottom: 2.5px solid #2b5c8a; padding-bottom: .3em; }
h2 { font-size: 13.5pt; margin: 1.6em 0 .5em; color: #2b5c8a;
     border-bottom: 1px solid #d5dde5; padding-bottom: .18em;
     break-after: avoid; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 1.2em 0 .4em; color: #333;
     break-after: avoid; page-break-after: avoid; }
p { margin: .5em 0; }
ul, ol { margin: .45em 0; padding-left: 1.5em; }
li { margin: .28em 0; }
li > ul, li > ol { margin: .25em 0; }
strong { color: #111; }
em { color: #333; }
code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 9pt;
       background: #f2f4f7; padding: .1em .32em; border-radius: 3px; }
pre { background: #f7f8fa; border: 1px solid #e2e6ec; border-radius: 4px;
      padding: .7em .9em; overflow-x: auto; }
pre code { background: none; padding: 0; font-size: 8.5pt; }
table { border-collapse: collapse; width: 100%; margin: .8em 0; font-size: 9.2pt;
        break-inside: avoid; page-break-inside: avoid; }
th, td { border: 1px solid #ccd4dd; padding: .4em .55em; text-align: left;
         vertical-align: top; }
th { background: #eef2f7; font-weight: 600; color: #1f4468; }
tbody tr:nth-child(even) { background: #fafbfc; }
blockquote { margin: .7em 0; padding: .1em 1em; border-left: 3px solid #c3cfdb;
             color: #444; }
hr { border: none; border-top: 1px solid #dde3ea; margin: 1.8em 0; }
a { color: #1f5c99; text-decoration: none; word-break: break-word; }
h2 + p, h2 + ul, h3 + p, h3 + ul { break-before: avoid; page-break-before: avoid; }
h2#sources ~ ol { font-size: 9pt; }
h2#sources ~ ol li { margin: .4em 0; }
"""


def find_chrome():
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser", "chrome", "msedge", "brave"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("error: no Chrome/Chromium found. Install Google Chrome, or add its path to CHROME_CANDIDATES.")


def render(md_path):
    md_path = os.path.abspath(md_path)
    if not os.path.exists(md_path):
        sys.exit(f"error: no such file: {md_path}")

    text = open(md_path, encoding="utf-8").read()
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "attr_list", "sane_lists", "md_in_html", "toc"],
    )
    title = html.escape(text.splitlines()[0].lstrip("# ").strip())
    page = (
        f'<!doctype html>\n<html><head><meta charset="utf-8"><title>{title}</title>\n'
        f"<style>{CSS}</style></head><body>\n{body}\n</body></html>"
    )

    pdf_path = os.path.splitext(md_path)[0] + ".pdf"
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "report.html")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(page)
        subprocess.run(
            [
                find_chrome(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path}",
                f"file://{html_path}",
            ],
            check=True,
            capture_output=True,
        )

    if not os.path.exists(pdf_path):
        sys.exit("error: Chrome ran but produced no PDF.")

    # Sanity check: tables must have survived the Markdown conversion.
    md_tables = sum(1 for line in text.splitlines() if line.lstrip().startswith("|"))
    if md_tables and "<table>" not in body:
        print("warning: source has pipe-tables but none rendered — check the 'tables' extension.")

    print(f"{pdf_path}  ({os.path.getsize(pdf_path) // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip())
    render(sys.argv[1])
