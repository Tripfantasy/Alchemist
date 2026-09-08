---
name: paper-reproduction
description: Turn a published paper into a runnable protocol or analysis notebook. Use whenever someone wants to reproduce, re-run, or reanalyze the experiments or computational analysis in a paper; asks for a step-by-step protocol from a paper or PDF; asks whether a paper's methods are complete enough to reproduce; wants the paper's GitHub code summarized into a documented workflow; or wants public data from an accession (GEO, SRA, ArrayExpress, Zenodo) pulled into a reanalysis. Also use for questions about what a paper fails to document, or which deposited file format to start from.
---

# Paper Reproduction

Read `workflows/paper_reproduction.md` and follow it. That file is the single
source of truth — do not work from memory or paraphrase its phases. For the
data-loading half, read `workflows/etl_geo.md` the same way.

## The four things that matter most

1. **Read the paper before asking intake questions.** Options built without
   reading it are generic, and a generic intake round targets the wrong figure.
   Skim abstract, Methods headings, and the Data/Code Availability statements
   first, then ask 3–4 questions in one batch naming this paper's actual figures.

2. **Every step carries a provenance tier: `stated` / `repo` / `inferred` /
   `missing`.** Never let an inference wear a citation's clothes. A clustering
   resolution you supplied because it is the tool default is `[inferred]`, and
   the researcher must be able to see that at a glance. Never cite a repo file
   or accession you have not actually fetched.

3. **What the paper fails to document is half the deliverable**, not an
   appendix. Rank gaps by whether they block reproduction, name the specific
   missing parameter rather than "methods are incomplete", and credit good
   documentation where it exists.

4. **Prefer processed data to raw reads.** Take the highest tier on the ladder
   in `workflows/etl_geo.md` — `.h5ad`/`.rds` > 10x `.h5` > MTX triplet > count
   table > BAM > FASTQ. Descending to FASTQ costs a week of compute and needs an
   explicit justification in the report.

## Hard constraints

- **No data downloads.** Probe accession metadata with `scripts/geo_probe.py`,
  then write the ETL code for the user to run. The notebook ships unrun.
- **Read-only outside the project.** Never edit, move, or copy anything under a
  globus directory.
- Use `./.venv/bin/python`, never bare `python3`.

## Deliverables

- `output/<first-author><year>_<topic>_protocol.md` **and** `.pdf` (render with
  `scripts/render_report.py` — the `.md` is the source of truth)
- `output/<first-author><year>_<topic>.ipynb` or `.Rmd` when the scope is
  computational — format mirrors the stack the paper's own authors used
