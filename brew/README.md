# Paper Reproduction Agent

Takes a published paper and produces (a) a step-by-step protocol report for its
wet-lab or computational methods, (b) a documented notebook that reproduces the
analysis from public data, and (c) an honest audit of what the paper does not
document well enough to reproduce.

## Setup

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

That installs `markdown` for the PDF renderer and nothing else — see
"What it deliberately does not do" below. Headless Chrome (already present on
macOS with Chrome installed) does the PDF conversion.

## Use

```
/brew https://doi.org/10.1038/s41593-024-xxxxx   what does Fig. 2 take to redo?
/brew ~/Downloads/paper.pdf
```

Or describe a paper you want reproduced and the `paper-reproduction` skill
triggers. Both route to `workflows/paper_reproduction.md`, which is the single
source of truth for the procedure.

The agent reads the paper first, then asks 3–4 intake questions naming that
paper's actual figures, then works. Expect to be asked which figure you want —
reproducing all of them produces a document nobody runs.

## What you get

- `output/<author><year>_<topic>_protocol.md` **and** `.pdf` — numbered steps,
  environment, data provenance, and the gap audit
- `output/<author><year>_<topic>.ipynb` or `.Rmd` — the notebook, ships unrun,
  format mirroring the stack the paper's own authors used

## The idea that carries the whole thing

Every step is tiered, and the tiers never blur:

| Tier | Means |
| --- | --- |
| `stated` | Explicit in the paper — cites the section |
| `repo` | Read out of the authors' code — cites `file.py:L40` |
| **[inferred]** | A tool default or field convention *this agent* supplied |
| `missing` | Not recoverable from any source |

A protocol that silently mixes what the authors wrote with what the agent
assumed is worse than no protocol, because the reader cannot tell which parts
to trust. The renderer color-codes the tiers so they survive into print.

## What it deliberately does not do

- **Download data.** `scripts/geo_probe.py` reads accession metadata and
  supplementary *listings*, and asks for sizes with HTTP HEAD. A GET on
  anything that looks like a payload is refused in code, not just avoided by
  convention.
- **Run the analysis.** Notebooks ship with empty outputs. Fabricated cell
  output would be indistinguishable from a real run.
- **Install an analysis environment.** The notebook mirrors the paper's stack
  and declares its own dependencies; this venv is the agent's tooling only.

## Layout

```
workflows/paper_reproduction.md   the procedure — read this first
workflows/etl_geo.md              accession -> format ladder -> loader
resources/protocol_report_template.md
resources/notebook_scaffold.md    notebook section order and conventions
resources/geo_reference.md        accession patterns, URLs, reference builds
resources/method_gaps.md          checklist of routinely-omitted method details
scripts/geo_probe.py              metadata-only accession probe
scripts/make_notebook.py          JSON step spec -> .ipynb / .Rmd
scripts/render_report.py          .md -> .pdf
data/<ACCESSION>/                 landing zone, gitignored, written by YOU
output/                           deliverables
```

## Scripts, directly

```bash
./.venv/bin/python scripts/geo_probe.py GSE174367 \
    --out data/GSE174367/probe.json --samples-csv data/GSE174367/samples.csv

./.venv/bin/python scripts/make_notebook.py spec.json \
    --out output/name.ipynb --strict

./.venv/bin/python scripts/render_report.py output/name_protocol.md
```

`geo_probe.py` reports the format tier **per file**, so a multi-assay series
(snRNA `.h5` next to an snATAC peak `.h5`, a bulk `.rda` next to both) doesn't
resolve to one misleading recommendation. It flags normalized tables, raw
matrices, ATAC features masquerading as expression, legacy CellRanger naming,
multi-organism series, and sample-count mismatches against the paper.

`make_notebook.py --strict` refuses to write a notebook whose spec breaks the
conventions — an inferred parameter with no explanation, a missing config cell,
or pasted outputs.

## Literature connectors

PubMed, bioRxiv, and Scite are authorized and working (verified 2026-09-08), and
the workflow prefers them over the open web for method extraction. Their schemas
are deferred, so the agent loads them with `ToolSearch` on demand.

What each is good for, and its catch:

- **Scite** — `search_literature` with `dois` + `term` returns full-text
  excerpts for the passage you asked about; query once per method section.
  Carries `editorialNotices` (retraction/correction check) and an `access` link
  for paywalled text. Excerpts are OA-only.
- **PubMed** — citation → PMID → PMCID → PMC full text
  (`convert_article_ids`, then `get_full_text_article`). Only ~6M articles have
  PMC full text. Content from it must cite PubMed and the article DOI.
- **bioRxiv** — `get_preprint` by DOI. `search_preprints` filters by date and
  category only, with **no keyword search**, so it can't find a named preprint.

Still not authorized: Box, ChEMBL, Gmail, Google Calendar, Google Drive,
Microsoft 365, Zoom. None are needed by this workflow.

The connectors don't relax any rule that matters: method text still tiers as
`stated` only for what it literally says, repo files and accessions still have
to be fetched before they're cited, and no data gets downloaded.
