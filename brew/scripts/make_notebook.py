"""Build the reproduction notebook (.ipynb or .Rmd) from a JSON step spec.

Why a scaffolder instead of writing the file directly: hand-authored notebook
JSON is easy to get subtly wrong (cell ids, nbformat minor version, source
arrays), and the failure shows up as "Jupyter can't open this file" rather than
as a diff. The spec is also reviewable -- you can read the step list and its
provenance without reading around boilerplate.

It also *checks* the conventions in resources/notebook_scaffold.md rather than
trusting them: an inferred parameter with no note, a missing config cell, or a
fabricated output all get flagged before the notebook ships.

Spec
----
{
  "title":    "Reproducing Fig. 2 -- snRNA-seq clustering",
  "paper":    "Chen et al. (2024), Nat Neurosci. 10.1038/s41593-024-xxxxx",
  "language": "python",              // or "r"
  "reproduces": "Fig. 2b-d",
  "not_covered": "Fig. 5 patch-clamp (no deposited data)",
  "accession": "GSE214435",
  "cells": [
    {
      "id":   "config",             // 'environment' and 'config' are expected
      "md":   "Every tunable parameter lives here.",
      "code": "ACCESSION = 'GSE214435'",
      "tier": "stated",             // stated | repo | inferred | missing
      "source": "Methods, 'Clustering'",
      "note": "raise to 1.2 for finer clusters",   // required when inferred
      "checkpoint": "paper reports 12,483 cells",
      "eval": false                 // .Rmd only: chunk needs data not yet fetched
    }
  ]
}

Usage
-----
  ./.venv/bin/python scripts/make_notebook.py spec.json --out output/chen2024.ipynb
  ./.venv/bin/python scripts/make_notebook.py spec.json --out output/chen2024.Rmd
  ./.venv/bin/python scripts/make_notebook.py spec.json --out x.ipynb --strict
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

TIERS = ("stated", "repo", "inferred", "missing")

KERNELS = {
    "python": {
        "kernelspec": {"display_name": "Python 3", "language": "python",
                       "name": "python3"},
        "language_info": {"name": "python", "file_extension": ".py",
                          "mimetype": "text/x-python", "version": "3.11"},
    },
    "r": {
        "kernelspec": {"display_name": "R", "language": "R", "name": "ir"},
        "language_info": {"name": "R", "file_extension": ".r",
                          "mimetype": "text/x-r-source", "version": "4.4"},
    },
}

TIER_BADGE = {
    "stated": "`stated`",
    "repo": "`repo`",
    "inferred": "**[inferred]**",
    "missing": "`missing`",
}


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def validate(spec: Dict) -> List[str]:
    """Return convention violations. Empty list means the spec is clean."""
    problems: List[str] = []

    for field in ("title", "language", "cells"):
        if not spec.get(field):
            problems.append("spec is missing required field '{}'".format(field))
    if spec.get("language") not in KERNELS:
        problems.append("language must be 'python' or 'r', got {!r}".format(
            spec.get("language")))
    if not spec.get("paper"):
        problems.append("no 'paper' citation -- the header must name what this "
                        "reproduces")

    cells = spec.get("cells") or []
    ids = [c.get("id", "") for c in cells]
    for expected, why in (
        ("environment", "cell 1 must print package versions "
                        "(sc.logging.print_versions() / sessionInfo())"),
        ("config", "every accession, path and threshold belongs in one config "
                   "cell, not scattered inline"),
    ):
        if expected not in ids:
            problems.append("no cell with id '{}': {}".format(expected, why))

    for i, cell in enumerate(cells, start=1):
        where = "cell {} ({})".format(i, cell.get("id") or "unnamed")
        if not cell.get("md") and not cell.get("code"):
            problems.append("{}: empty -- needs 'md', 'code', or both".format(where))
        tier = cell.get("tier")
        if tier and tier not in TIERS:
            problems.append("{}: tier {!r} is not one of {}".format(
                where, tier, ", ".join(TIERS)))
        if tier == "inferred" and not cell.get("note"):
            problems.append(
                "{}: inferred steps need a 'note' saying what was assumed and "
                "what changing it would do -- an unexplained inference is the "
                "failure mode the whole provenance scheme exists to prevent"
                .format(where))
        if tier in ("stated", "repo") and not cell.get("source"):
            problems.append("{}: tier '{}' needs a 'source' (paper section, or "
                            "file:line in the authors' repo)".format(where, tier))
        if cell.get("outputs"):
            problems.append(
                "{}: spec carries 'outputs'. This project ships notebooks "
                "unrun -- never paste fabricated results into cells."
                .format(where))
    return problems


# --------------------------------------------------------------------------
# shared rendering
# --------------------------------------------------------------------------

def _header_md(spec: Dict, include_h1: bool = True) -> str:
    # .Rmd renders its title from the YAML header, so repeating it as an H1
    # gives the knitted document two titles.
    lines = ["# {}".format(spec["title"]), ""] if include_h1 else []
    lines.append("**Paper:** {}".format(spec["paper"]))
    if spec.get("reproduces"):
        lines.append("**Reproduces:** {}".format(spec["reproduces"]))
    if spec.get("not_covered"):
        lines.append("**Not covered:** {}".format(spec["not_covered"]))
    if spec.get("accession"):
        lines.append("**Data:** {}".format(spec["accession"]))
    lines += [
        "",
        "**Provenance tiers** — every step below is labelled: `stated` (in the "
        "paper) · `repo` (in the authors' code) · **[inferred]** (supplied by "
        "this notebook, not the authors) · `missing` (unrecoverable).",
        "",
        "**This notebook ships unrun.** No data has been downloaded. Run the "
        "ETL cell first; expected download size is in the protocol report.",
        "",
        "Cluster numbering is arbitrary — never match clusters to the paper's "
        "by number, match on markers.",
    ]
    return "\n".join(lines)


def _step_md(cell: Dict) -> str:
    """One markdown block: what the step does, its provenance, its checkpoint."""
    parts: List[str] = []
    if cell.get("md"):
        parts.append(cell["md"].rstrip())
    tier = cell.get("tier")
    if tier:
        line = TIER_BADGE[tier]
        if cell.get("source"):
            line += " — *{}*".format(cell["source"])
        if tier == "inferred" and cell.get("note"):
            line += " — {}".format(cell["note"])
        parts.append(line)
    elif cell.get("note"):
        parts.append(cell["note"])
    if cell.get("checkpoint"):
        parts.append("**Checkpoint:** {}".format(cell["checkpoint"]))
    if cell.get("cost"):
        parts.append("**Cost:** {}".format(cell["cost"]))
    return "\n\n".join(parts)


# --------------------------------------------------------------------------
# .ipynb
# --------------------------------------------------------------------------

def _nb_cell(kind: str, text: str, index: int) -> Dict:
    source = text.splitlines(keepends=True)
    cell = {
        "cell_type": kind,
        "id": "cell-{:02d}".format(index),
        "metadata": {},
        "source": source,
    }
    if kind == "code":
        cell["execution_count"] = None
        cell["outputs"] = []          # ships unrun, always
    return cell


def build_ipynb(spec: Dict) -> str:
    cells: List[Dict] = [_nb_cell("markdown", _header_md(spec), 0)]
    n = 1
    for cell in spec["cells"]:
        md = _step_md(cell)
        if md:
            cells.append(_nb_cell("markdown", md, n))
            n += 1
        if cell.get("code"):
            cells.append(_nb_cell("code", cell["code"].rstrip(), n))
            n += 1
    nb = {
        "cells": cells,
        "metadata": KERNELS[spec["language"]],
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(nb, indent=1) + "\n"


# --------------------------------------------------------------------------
# .Rmd
# --------------------------------------------------------------------------

def _chunk_name(cell: Dict, index: int) -> str:
    """knitr chunk names must be unique and non-empty; its errors are otherwise
    unreadable ("Error in chunk 7")."""
    raw = cell.get("id") or (cell.get("md") or "step").splitlines()[0]
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:40]
    return slug or "step-{:02d}".format(index)


def build_rmd(spec: Dict) -> str:
    lang = "python" if spec["language"] == "python" else "r"
    out: List[str] = [
        "---",
        'title: "{}"'.format(spec["title"].replace('"', "'")),
        'output:',
        '  html_document:',
        '    toc: true',
        '    toc_float: true',
        '    code_folding: show',
        "---",
        "",
        "```{r setup, include=FALSE}",
        "knitr::opts_chunk$set(echo = TRUE, message = FALSE, warning = FALSE)",
        "```",
        "",
        _header_md(spec, include_h1=False),
        "",
    ]
    if spec["language"] == "python":
        # Warn only -- never touch `out`, the YAML block must be line 1.
        print("  note: a python spec written to .Rmd produces {python} chunks, "
              "which need reticulate. Prefer .ipynb for a python paper.",
              file=sys.stderr)
    seen: Dict[str, int] = {}
    for i, cell in enumerate(spec["cells"], start=1):
        md = _step_md(cell)
        if md:
            out += [md, ""]
        if not cell.get("code"):
            continue
        name = _chunk_name(cell, i)
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = "{}-{}".format(name, seen[name])
        # knitr syntax: engine and label are SPACE-separated, and only the
        # options after them are comma-separated. "{r, name}" is invalid.
        header = "{} {}".format(lang, name)
        if cell.get("eval") is False:
            header += ", eval=FALSE"
        out += ["```{{{}}}".format(header),
                cell["code"].rstrip(), "```", ""]
    out += ["```{r session-info}", "sessionInfo()", "```", ""]
    return "\n".join(out)


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path, help="JSON step spec")
    ap.add_argument("--out", type=Path, required=True,
                    help="output path; .ipynb or .Rmd decides the format")
    ap.add_argument("--strict", action="store_true",
                    help="refuse to write when any convention check fails")
    args = ap.parse_args()

    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit("cannot read spec: {}".format(e))

    problems = validate(spec)
    fatal = [p for p in problems if "missing required field" in p
             or "language must be" in p]
    if problems:
        print("convention checks ({} issue(s)):".format(len(problems)))
        for p in problems:
            print("  ! {}".format(p))
    if fatal or (problems and args.strict):
        sys.exit("not writing: fix the issues above (or drop --strict)")

    suffix = args.out.suffix.lower()
    if suffix == ".ipynb":
        text = build_ipynb(spec)
    elif suffix in (".rmd", ".qmd"):
        text = build_rmd(spec)
    else:
        sys.exit("--out must end in .ipynb or .Rmd, got {}".format(suffix))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    n_code = sum(1 for c in spec["cells"] if c.get("code"))
    print("wrote {}  ({} steps, {} code cells, unrun)".format(
        args.out, len(spec["cells"]), n_code))


if __name__ == "__main__":
    main()
