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
3. **Whether processed files exist.** This decides the entire shape of the
   reproduction (Step 2).

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
