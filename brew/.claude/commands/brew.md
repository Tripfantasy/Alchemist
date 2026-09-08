---
description: Turn a paper into a runnable protocol or analysis notebook, plus an audit of what it fails to document
argument-hint: "[paper URL, DOI, PMID, or path to a PDF] [what you want from it]"
---

Run the paper reproduction workflow.

**Read `workflows/paper_reproduction.md` now and follow it.** That file is the
single source of truth for this procedure — do not work from memory, and do not
paraphrase its phases. If anything here conflicts with it, that file wins. For
the data-loading half, read `workflows/etl_geo.md` the same way.

## The paper

$ARGUMENTS

If that is empty, ask for a paper before doing anything else. A DOI, PMID, URL,
or local `.pdf` path all work.

## Order of operations

1. **Read the paper first** — abstract, Methods headings, and above all the
   **Data Availability and Code Availability statements**. Those two paragraphs
   decide whether reproduction is possible at all.
2. **Then** ask 3–4 intake questions in one `AskUserQuestion` call, with options
   naming this paper's actual figures and datasets. Never a generic
   "broad vs. detailed" round.
3. Show the plan, then proceed without waiting for approval.

## Standing context

- **No data downloads.** `scripts/geo_probe.py` fetches accession metadata and
  file listings only; it refuses payloads. The notebook ships unrun, with
  accessions and paths wired in for the user to run.
- Data lands under `data/<ACCESSION>/` when the *user* runs the ETL — gitignored,
  with `probe.json` and `samples.csv` beside the payloads.
- **Always use `./.venv/bin/python`**, never bare `python3`.
- Notebook format **mirrors the paper's own stack** — `.ipynb` for
  Python/scanpy papers, `.Rmd` for R/Seurat/Bioconductor. The project ships no
  analysis environment of its own; the notebook declares its own.
- The PubMed / bioRxiv / Scite connectors **are authorized and working**. Their
  schemas are deferred — load them with `ToolSearch` first. Prefer them over the
  open web for method text; `WebSearch`/`WebFetch` remain the fallback and the
  only route to a GitHub repo. The workflow's Tool note has the full preference
  ladder and the per-connector gotchas.
- **Check for retractions and corrections** via Scite's `editorialNotices`
  before building a protocol from a paper, and report the result either way.

## Non-negotiable

**Never launder an inference into a fact.** Every step is tiered `stated`,
`repo`, `inferred`, or `missing`. A plausible parameter the paper never gave is
`[inferred]` with the assumption spelled out — writing it bare is fabrication,
and it is the failure mode most likely to slip through unnoticed.

**Never cite a repo file or accession you have not fetched.** A repo URL printed
in a paper is not proof of a working repo; 404s and empty repos are routine.

## Deliverable

Both `.md` and `.pdf` in `output/`, per `resources/protocol_report_template.md`:

```bash
./.venv/bin/python scripts/render_report.py output/<name>_protocol.md
```

Plus the notebook, when the scope is computational — built with
`scripts/make_notebook.py`, following `resources/notebook_scaffold.md`. Hand back
the file paths, the biggest reproduction risk, and the first command to run
with its expected download size.
