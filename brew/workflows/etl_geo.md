# Workflow: Public Data ETL

**Purpose:** Turn an accession named in a paper into a loading step a researcher
can run — the right files, in the right format, with sample labels that match
the paper's figures.

Called from `workflows/paper_reproduction.md` Phase 2. Not usually run alone,
though `/brew` on a bare accession is a legitimate use.

**Standing constraint:** this project **does not download data files**. It probes
metadata, decides which files are the right ones, and writes the ETL code the
user runs. `scripts/geo_probe.py` enforces the line — it fetches listings and
metadata only, and refuses to retrieve payloads.

---

## Step 1 — Probe the accession

```bash
./.venv/bin/python scripts/geo_probe.py GSE214435 --out data/GSE214435/probe.json
```

Prints, and records: series title, platform(s), sample count, sample titles with
their GEO characteristics, the supplementary file listing with sizes, any linked
SRA project, and the format tier it resolved to (Step 2).

Read the JSON before writing any loader. Three things to check first:

1. **The accession resolves at all.** Embargoed and mistyped accessions are
   common in accepted-but-not-yet-public papers. If it 404s, that is an
   *inaccessible asset* gap — report it, don't work around it.
2. **Sample count matches the paper.** A paper describing 8 samples against a
   6-sample series means samples live in a second accession, a SuperSeries, or
   were never deposited. Resolve this now, not after writing the loader.
3. **Whether processed files exist**, and **what state they are in.** These are
   two different questions. `format.tier` answers the first; `processing.state`
   answers the second (Step 2b). Together they decide the entire shape of the
   reproduction — the tier decides which file you load, the state decides
   whether the QC steps run at all.

For a SuperSeries, probe the sub-series too — the files live there, not on the
parent.

---

## Step 2 — The format preference ladder

Take the highest tier available. Never descend a tier for convenience, and never
climb to raw reads when a processed matrix exists.

| Tier | Format | Why |
| --- | --- | --- |
| **1** | `.h5ad` / `.rds` / `.qs` / `.loom` | Fully processed object — often carries the authors' own clustering and annotations, so figures are directly comparable |
| **2** | `.h5` (10x HDF5, filtered) | One file per sample, fast, unambiguous. **The default target for 10x papers.** |
| **3** | MTX triplet (`matrix.mtx.gz` + `barcodes.tsv.gz` + `features.tsv.gz`) | Equivalent content, three-file fragility (see Step 4) |
| **4** | Per-gene count table (`.csv`/`.txt`/`.tsv`) | Fine for bulk RNA-seq; for single-cell it means a dense matrix and a memory problem |
| **5** | BAM / CRAM | Realignment territory. Only when the question is alignment-dependent (e.g. allele-specific expression, novel isoforms) |
| **6** | FASTQ via SRA | **Last resort.** Days of compute, hundreds of GB, and a rebuilt reference. Justify it explicitly in the report |

**When to legitimately descend to Tier 5–6:**

- The processed matrix was built on a reference build that can't answer the
  question (e.g. a transgene or a knock-in allele absent from the reference)
- The question is about something quantification discards — splicing, editing,
  allele-specific expression, TCR/BCR sequence
- Only raw data was deposited

Otherwise, descending is a choice to spend a week regenerating a file the authors
already published. Say so before doing it.

⚠️ Tier 1 objects carry the authors' *conclusions*, not just their data. Loading
their `.h5ad` and re-plotting their UMAP is a figure check, not a reproduction —
if the goal is to verify their pipeline, start from Tier 2/3 counts and rebuild.
Say which one you did.

---

## Step 2b — Is the data already processed?

Tier says what *format* the files are. This step says what *state* they are in —
whether cell-calling and QC filtering already ran before deposition. The two are
independent, and getting this wrong breaks a reproduction quietly.

**The failure it prevents.** The paper's QC section says `min_genes=200,
max_mito=10`. You write those thresholds into the notebook, faithfully. But the
deposited matrix was already filtered by the authors on the same criteria, so
the notebook filters an already-filtered matrix — and reports 9,900 cells where
the paper says 12,483. The numbers disagree, both steps are individually
correct, and nothing in the notebook shows why. A researcher then spends a day
hunting a bug in the reproduction that is actually a double-filter.

`geo_probe.py` resolves this. Read `processing.state` from the probe JSON:

| `state` | Means | What the notebook does with QC |
| --- | --- | --- |
| `raw` | Raw droplets, pre-cell-calling | **Live cells.** QC is genuinely part of this reproduction |
| `processed` | Cell-called and/or QC-filtered upstream | **Commented cells** — see below |
| `mixed` | Both deposited | You choose, and say why. Raw to verify their pipeline; processed to build on their result |
| `unknown` | No signal either way | **Live cells, plus the dimension check below** |

`processing.evidence` names the files behind the call, and `processing.guidance`
carries the per-state instruction. Quote the evidence in the report — a caveat
you cannot trace to a filename becomes vague hedging.

### This is `[inferred]`, never `stated`

The probe reads filenames and the series text. Neither is proof: the only proof
is the file header, and reading it means downloading, which this project does not
do. So a processing-state call is an **[inferred]** tier step, and it says what
it was inferred from:

> **[inferred — deposit appears pre-filtered; `GSM8145_filtered_feature_bc_matrix.h5`
> carries CellRanger's `filtered` prefix. The paper's QC thresholds are recorded
> in the commented cell below. Uncomment if your matrix dimensions indicate raw
> droplets.]**

Never write "the data is already filtered" flat. The probe did not open the file.

### The commented-QC convention (`state: processed`)

QC steps ship **present but inert** — never deleted, never live. Deleting them
loses the paper's thresholds and makes the notebook look like it skipped a step
the paper documented; running them double-filters.

Each commented block carries four things, in this order:

1. **Why it is commented** — one line, naming the evidence file
2. **The paper's actual thresholds**, preserved verbatim with their tier
3. **When to uncomment** — the concrete condition, not "if needed"
4. **What changes if you do** — so the researcher can predict the effect

```python
# ---------------------------------------------------------------------
# QC filtering -- COMMENTED BY DEFAULT
#
# Why: GSM8145_filtered_feature_bc_matrix.h5 is CellRanger `filtered`
#      output, so cell-calling and the authors' QC already ran. Applying
#      these thresholds again double-filters and undercounts cells.
#      [inferred from the filename -- the probe did not open the file]
#
# The paper's thresholds, preserved:
#   min_genes = 200      # stated (Methods, "Quality control")
#   max_mito  = 10.0     # stated (Methods, "Quality control")
#
# Uncomment IF: the dimension check above prints a cell count far ABOVE
#      the paper's 12,483 -- that means you loaded raw droplets, not the
#      filtered matrix, and these thresholds are needed after all.
# Effect: drops ~N barcodes; expect the count to land near the paper's.
# ---------------------------------------------------------------------
# sc.pp.filter_cells(adata, min_genes=200)
# adata = adata[adata.obs.pct_counts_mt < 10.0].copy()
```

For `.Rmd`, use a named chunk with `eval=FALSE` and the same four-part header —
the chunk stays visible and knits, it just does not run.

### The dimension check (every state, including `processed`)

Whatever the state, the ETL prints dimensions *before* any QC cell and compares
against the paper. This is what makes a wrong inference visible in one line
instead of a day:

```python
print(f"loaded: {adata.n_obs:,} cells x {adata.n_vars:,} genes")
print(f"paper reports {12483:,} after QC")
print("-> well above the paper's count: raw droplets, QC cells needed (uncomment)")
print("-> at or near the paper's count: already filtered, leave QC commented")
```

For `state: unknown` this check is not optional — it is the entire mechanism by
which the state gets resolved, and its markdown cell says so.

### Modality changes what "QC" even means

The commented block is not always about `min_genes` / `max_mito`. Branch on the
assay before writing it — the probe's `format.flags` name the modality:

| Modality | The QC that may already have run |
| --- | --- |
| scRNA / snRNA | Cell-calling, min genes/counts, mito %, doublet removal |
| ATAC / Multiome | Peak calling, TSS enrichment, nucleosome signal, FRiP |
| CITE-seq / hashing | Demultiplexing, negative/doublet classification by HTO |
| Spatial | Under-tissue spot filtering — a spot matrix may be tissue-restricted already |
| Bulk RNA-seq | Low-count gene filtering, and **whether the values are normalized at all** (Step 4) |

A deposit that is filtered for RNA may be entirely unfiltered for its ATAC half.
State per modality, not per series.

---

## Step 3 — Map samples to the paper's conditions

The single most error-prone step, and the one that silently ruins downstream DE.
GEO sample titles are author-authored free text and often don't match the
figure labels at all.

- Build an explicit **sample sheet** — never infer condition from file order.
  `GSM6612345` → `title`, `condition`, `genotype`, `sex`, `age`, `replicate`,
  `batch`, and the file it maps to.
- Source the labels from GEO `characteristics_ch1` fields where present; fall
  back to the paper's supplementary sample table.
- **Check n per group against the paper.** "3 WT vs 3 KO" in a figure legend
  against 4-and-2 in the series means you have mislabeled something, or the
  paper dropped a sample it never mentioned dropping. Either way, stop and
  resolve it.
- Sample titles like `WT_1`, `WT_2`, `Mut_1` are the easy case. Titles like
  `Sample_A_run2` require the supplementary table, and if that's missing the
  mapping is `missing` tier — a blocking gap, not an inference to guess at.
- Batch is worth capturing even when the paper ignores it. Sequencing runs
  visible in the sample metadata often explain variance the paper attributes
  elsewhere.

Write the sample sheet to `data/<GSE>/samples.csv` and have the notebook read it.
A hardcoded sample-to-condition dict inside the notebook is unreviewable.

---

## Step 4 — Write the loader

Conventions for the ETL cells, whatever the stack:

- **Idempotent.** Check for the file before fetching; skip if present and the
  size matches the probe. A researcher will re-run the notebook.
- **Everything lands under `data/<GSE>/`** — gitignored, one directory per
  accession, `probe.json` and `samples.csv` beside the payloads.
- **Verify after fetch, before use.** Row/column counts, and gene symbols that
  look like the right organism. A truncated download reads as a valid file.
- **Print dimensions and compare to the paper.** "Paper: 12,483 cells after QC.
  Here: {n}." A silent mismatch is how a reproduction goes wrong invisibly.
- **Parameterize the accession and paths at the top** — never sprinkled inline.
- Use the paper's reference build, not the current one, and say which.

### Python (Tier 2, per-sample `.h5`)

```python
import scanpy as sc, pandas as pd, pathlib

DATA = pathlib.Path("data/GSE214435")
samples = pd.read_csv(DATA / "samples.csv")

adatas = {}
for row in samples.itertuples():
    a = sc.read_10x_h5(DATA / row.file)
    a.var_names_unique()                      # duplicate symbols are common
    a.obs["sample"] = row.gsm                 # before concat, or it's lost
    a.obs["condition"] = row.condition
    adatas[row.gsm] = a

adata = sc.concat(adatas, label="sample_id", index_unique="-")
print(adata.shape)   # compare to the paper's reported cell count
```

### R (Tier 3, MTX triplet)

```r
library(Seurat); library(Matrix)
samples <- read.csv("data/GSE214435/samples.csv")

objs <- lapply(seq_len(nrow(samples)), function(i) {
  m <- Read10X(file.path("data/GSE214435", samples$dir[i]))
  o <- CreateSeuratObject(m, project = samples$gsm[i])
  o$condition <- samples$condition[i]
  o
})
obj <- merge(objs[[1]], objs[-1], add.cell.ids = samples$gsm)
dim(obj)
```

### Bulk RNA-seq (Tier 4)

Counts table + sample sheet into `DESeq2`/`edgeR`. Check whether the deposited
table is raw counts, TPM, FPKM, or already log-transformed — **a paper's
"expression matrix" is often normalized**, and feeding normalized values to
DESeq2 is invalid. If the header doesn't say, the units are `missing` tier.

---

## Step 5 — Known GEO traps

Each of these has silently broken a real reanalysis:

- **`features.tsv.gz` vs `genes.tsv.gz`.** CellRanger ≤2 wrote `genes.tsv`
  (2 columns); ≥3 writes `features.tsv` (3 columns, with feature type).
  `Read10X` and `read_10x_mtx` expect names matching their era. Renaming files
  to satisfy a loader is normal and worth documenting.
- **Author-prefixed filenames.** GEO prepends `GSM6612345_`, so a directory of
  `GSM6612345_WT1_barcodes.tsv.gz` files will not load as a 10x directory. The
  loader must strip prefixes into per-sample directories — this is the most
  common first failure.
- **Feature-barcode multiplexing.** A `.h5` from CITE-seq or Multiome carries
  Antibody Capture or Peaks alongside Gene Expression. Split by feature type
  before analysis or the counts are nonsense.
- **Filtered vs raw matrices.** `raw_feature_bc_matrix` includes empty droplets.
  If the paper's cell count is far below yours, you loaded raw. If far above,
  they used a different cell-calling threshold.
- **Barcode suffixes.** `-1` suffixes collide across samples on merge. Set
  `index_unique` / `add.cell.ids` — silent barcode collisions drop cells.
- **Ensembl IDs vs symbols.** Papers report symbols; matrices often carry
  Ensembl IDs. Mapping is lossy in both directions; note which you used.
- **Mouse vs human gene case.** `Gfap` vs `GFAP`. A case-insensitive match
  covering a species mix-up is worse than a failure.
- **Supplementary `.tar` bundles.** A single series-level `.tar` holding all
  samples must be extracted before anything else; the probe reports its size,
  which is the real download cost.
- **`processed` files that are actually Seurat objects saved as `.rds` from an
  old Seurat version.** They may not load in current Seurat without
  `UpdateSeuratObject`, and sometimes not at all.

---

## Step 6 — Record what the ETL cost and what it can't do

Into the report's Data section:

- Accession(s), tier taken, **total download size**, and rough download time
- **Processing state, the evidence for it, and which QC steps ship commented as
  a result.** Say it plainly: "the deposit appears pre-filtered (`…filtered_feature_bc_matrix.h5`),
  so the paper's QC thresholds are preserved as commented cells rather than run.
  This is inferred from filenames — confirm against the loaded dimensions."
  A reader must never have to open the notebook to discover a documented step
  is inert.
- Sample sheet summary: n per group as deposited, vs n per group as the paper
  describes
- Files that exist but were **not** used, and why (raw matrices, unrelated assays)
- What this tier cannot answer — Tier 2/3 cannot address splicing or
  allele-specific questions; Tier 1 cannot verify the authors' own pipeline
- Controlled-access components (dbGaP, EGA): the exact application route, and
  say plainly that reproduction is blocked until it clears

---

## Non-GEO sources, briefly

- **SRA/ENA** — prefer **ENA** for FASTQ; it serves them directly over HTTPS/FTP
  without `fasterq-dump`. `ffq` resolves accession → URLs.
- **Zenodo/figshare** — stable DOIs, and often the intermediate objects the
  GitHub repo omits. Usually Tier 1.
- **Synapse** — registration and often a data-use agreement. Needs `synapseclient`.
- **ArrayExpress/BioStudies** — same ladder; `E-MTAB-####`.
- **CELLxGENE / Human Cell Atlas / Allen** portals — curated `.h5ad` of published
  data, sometimes cleaner than the original GEO deposit. Worth checking for
  well-known datasets, but they are *re-curated*, so state that.
- **UCSC Cell Browser / Single Cell Portal** — good for confirming annotations
  and marker genes without downloading anything.
