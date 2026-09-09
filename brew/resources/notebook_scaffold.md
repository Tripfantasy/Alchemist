# Notebook Conventions

How the `.ipynb` / `.Rmd` deliverable is structured. Build it with
`scripts/make_notebook.py` rather than hand-writing notebook JSON.

## The one test the notebook must pass

**A researcher who has never seen the paper can run it top to bottom on a clean
machine and know, at each step, whether they got what the paper got.**

Everything below serves that. If a convention here conflicts with it, the test wins.

## Section order

Fixed, so every notebook in `output/` reads the same way:

| # | Section | Contents |
| --- | --- | --- |
| 0 | **Header** (markdown) | Citation + DOI, what this reproduces (Fig. N), what it does *not* cover, and the provenance-tier key |
| 1 | **Environment** (code) | Imports + printed versions. `sc.logging.print_versions()` / `sessionInfo()`. First cell, always |
| 2 | **Config** (code) | Every accession, path, and threshold as a named constant. Nothing tunable appears anywhere below this cell |
| 3 | **ETL** (code) | Fetch → verify → sample sheet → **print dimensions**. Idempotent. See `workflows/etl_geo.md` |
| 4 | **QC + filtering** (code) | Live or commented, per the probe's `processing.state` — see below. Always carries the paper's reported counts as printed checkpoints |
| 5 | **Analysis** (code) | The paper's actual pipeline, one cell per conceptual step |
| 6 | **Figure reproduction** (code) | The target panel, captioned with what to compare against |
| 7 | **Divergences** (markdown) | Where this is known to depart from the paper, and why |
| 8 | **Session info** (code) | Printed at the end, so a saved run is self-documenting |

## Config cell

Every parameter the researcher might change lives here, with its tier as a
comment. This is what makes the notebook adaptable to their own data instead of
a one-off.

```python
ACCESSION   = "GSE214435"
DATA_DIR    = pathlib.Path("data") / ACCESSION
REFERENCE   = "GRCm39"      # stated (Methods, "Alignment")
MIN_GENES   = 200           # INFERRED - paper gives no cutoff; scanpy convention
MAX_MITO    = 10.0          # INFERRED - paper says "high mito removed", no value
N_HVG       = 2000          # stated (Methods, "Normalization")
RESOLUTION  = 0.8           # repo (analysis/cluster.R:L44)
SEED        = 0             # INFERRED - paper reports no seed; results will drift

# Checkpoints and deposit state -- what the dimension check compares against
PAPER_N_CELLS = 12483       # stated (Results, "12,483 cells passed QC")
DEPOSIT_STATE = "processed" # INFERRED from probe.json processing.state;
                            # section 4 QC is COMMENTED because of this
```

`PAPER_N_CELLS` and `DEPOSIT_STATE` are not optional. The first is what makes
divergence measurable; the second is what tells a reader, at the top of the
notebook, why a documented QC step is inert further down.

## Section 4 is conditional: live QC or commented QC

Whether the QC cells run depends on the state the data was deposited in, not on
what the paper's Methods section says. Read `processing.state` from
`data/<GSE>/probe.json` and follow `workflows/etl_geo.md` Step 2b.

| `processing.state` | Section 4 ships |
| --- | --- |
| `raw` | **Live cells.** The default, and the case the rest of this file assumes |
| `processed` | **Commented cells**, with the paper's thresholds preserved inside them |
| `mixed` | Live or commented per the file you actually loaded — state the choice in the section's markdown cell |
| `unknown` | **Live cells**, and the section's markdown cell tells the reader to check the printed dimensions first |

Three rules that hold in every state:

- **Never delete a QC step the paper documents.** Commented is not the same as
  absent. A deleted step tells the reader the paper omitted something it did
  not, and it throws away thresholds that took a Methods read to recover.
- **A commented cell is still tiered and still sourced.** `min_genes = 200` from
  the Methods stays `stated (Methods, "Quality control")` even inside a comment.
- **Say why, where the reader is.** The comment block names the evidence file and
  the condition for uncommenting. "Commented out" with no reason reads as an
  unfinished notebook.

The four-part comment header and a worked example are in `workflows/etl_geo.md`
Step 2b — follow that format rather than inventing one, so every notebook in
`output/` marks inert steps the same way.

### Section 3 always ends with the dimension check

This is what makes a wrong processing-state call visible immediately, so it
ships in every notebook regardless of state:

```python
print(f"loaded: {adata.n_obs:,} cells x {adata.n_vars:,} genes")
print(f"paper reports {PAPER_N_CELLS:,} cells after QC")
# far above  -> raw droplets: uncomment section 4
# at or near -> already filtered: leave section 4 commented
```

## Markdown cells

One before every code cell. Three lines, in this order:

1. **What this step does**, in a sentence a biologist reads without decoding code
2. **Tier + source** — `stated (Methods, "Clustering")`, `repo (cluster.R:L44)`,
   **`[inferred]`** with the assumption, or `missing`
3. **Checkpoint** — the number the paper reports, when there is one

An `[inferred]` cell says what to change and what changing it would do. That
sentence is the difference between a notebook someone adapts and one they abandon.

## Checkpoints

The mechanism that makes divergence visible instead of silent. After any step
the paper quantifies:

```python
print(f"cells after QC: {adata.n_obs:,}  (paper reports 12,483)")
print(f"clusters found: {adata.obs['leiden'].nunique()}  (paper reports 14)")
```

Never assert the match — print both and let the researcher see. A hardcoded
`assert` that fails on a clean run reads as a broken notebook.

## Hard rules

- **No hidden state.** No cell that only works if an earlier cell ran twice, and
  no reliance on a variable defined in a deleted cell.
- **No guessed identifiers.** Never write `adata.obs["celltype"]` or
  `obj$condition` unless you have confirmed the field exists — from the probe
  metadata, the repo, or a documented deposit. A notebook that dies on cell 3
  because a column name was invented is worse than one that stops early and
  says the field is unknown.
- **No silent overwrites.** ETL checks before fetching; nothing outside
  `data/<ACCESSION>/` is written.
- **No QC step applied to data that already had it.** Check `processing.state`
  before writing section 4. Double-filtering produces a cell count below the
  paper's, from two individually correct steps, with nothing in the notebook
  showing the cause — the hardest class of reproduction bug to find.
- **No documented step silently deleted.** If a step does not run, it ships
  commented with its thresholds and the reason, never removed.
- **Long steps flagged, not hidden.** A cell that takes 40 minutes or 60 GB of
  RAM says so in its markdown cell, above the code.
- **Cluster numbering is arbitrary.** Never claim "cluster 3 is the paper's
  cluster 3" — match on markers, and say so.
- **Attribute lifted code.** Code adapted from the authors' repo carries the
  source path in a comment. Their license governs redistribution; note it in the
  header if the repo has one.

## Format choice

Mirror the stack the paper's authors used — `.ipynb` for Python/scanpy work,
`.Rmd` for R/Seurat/Bioconductor. Code lifts across directly and a reader
comparing the notebook to the repo sees the same idioms. Mixed repo: follow
whatever produced the *target figure*. No repo: choose from the tools the paper
names, and state the choice in the header.

`.Rmd` specifics:

- YAML header with `title`, `output: html_document`, `date`
- `knitr::opts_chunk$set(echo = TRUE, message = FALSE)` in a `setup` chunk
- Named chunks (`{r qc-filtering}`) — knitr errors are unreadable otherwise
- `eval=FALSE` on any chunk that needs data not yet downloaded, so the notebook
  knits before the ETL has been run

## Ship state

The notebook ships **unrun** — this project downloads no data. Outputs are empty
by design, and the header says so, along with the first command to run and the
expected download size. Do not paste fabricated outputs into cells.
