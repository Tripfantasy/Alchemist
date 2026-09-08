# Reproduction Protocol — <SHORT TITLE>

**Paper:** <First Author> et al. (<Year>), *<Journal>*. <DOI>
**Requested by:** <name> · **Date:** <YYYY-MM-DD>
**Scope:** <wet-lab | computational | both> · **Target:** <Fig. N / named analysis>
**Data:** <accessions, or "none deposited"> · **Code:** <repo URL, or "none found">

**Goal as understood:**
> <One or two sentences, from the intake answers. If you narrowed the target or
> assumed anything, say it here — this is what the protocol below delivers.>

---

## 0. Reproducibility at a glance

| | Status |
| --- | --- |
| Processed data deposited | <yes — Tier N `.h5` / no — raw reads only / embargoed> |
| Authors' code available | <yes, runs Fig. N / partial / none found> |
| Environment pinned | <`renv.lock` present / versions in text only / unstated> |
| Sample→condition mapping | <in GEO characteristics / supplementary table only / **unrecoverable**> |
| **Verdict** | <reproducible as written / reproducible with inferences / blocked — see §4> |

**Provenance tiers used below:** `stated` (in the paper) · `repo` (in the
authors' code) · **[inferred]** (supplied by this report) · `missing`
(unrecoverable). Every step carries one.

⚠️ <Delete if not applicable. The single most important caveat — e.g. "Steps 6–8
are inferred; the paper gives no filtering thresholds, so cluster counts will
not match Fig. 2 exactly.">

---

## 1. Environment

*Computational scope only — delete this section for a pure wet-lab protocol.*

**Stack:** <Python 3.11 / R 4.4.1> · **Source:** <repo `environment.yml` / paper text / [inferred]>

| Package | Version | Source |
| --- | --- | --- |
| `scanpy` | 1.10.1 | repo `environment.yml` |
| `scvi-tools` | 1.1.2 | Methods, "Integration" |
| `harmonypy` | unstated | **[inferred]** — latest; paper names the method, not the version |

**Reference:** <GRCm39 / mm10 / GRCh38-2020-A> · **Annotation:** <Ensembl 110 / GENCODE vM25>
**Recommended resources:** <N> cores · <N> GB RAM · <N> GB disk · ~<N> h wall-clock
**Setup:**

```bash
<conda env create -f environment.yml  |  renv::restore()>
```

⚠️ <Delete if not applicable. Version drift note — e.g. "the paper used Seurat
v4; v5 changed the default normalization and the assay class. Pin v4 or expect
different numbers.">

---

## 2. Protocol

Numbered so it can be worked through directly. Tier on every step.

### 2a. <Wet-lab phase name — e.g. Tissue dissociation>

*Delete this whole subsection for a computational-only request.*

1. **<Step name>** — `stated` *(Methods, "<subsection>")*
   - <Reagent, vendor, catalog #, concentration>
   - <Volume, temperature, duration, speed with units — `g` not RPM>
   - *Note:* <what a first-timer gets wrong here>
2. **<Step name>** — **[inferred]**
   - <What you supplied and why: "paper says 'standard dissociation'; this is
     the cited protocol [17] adapted to the stated tissue mass">

**Materials:** <table or bullets — reagents with catalog numbers, equipment>
**Animals/samples:** <strain, sex, age, n per group> · **Approval:** <IACUC/IRB as cited>
**Timeline:** <what must be prepped a day ahead; total hands-on time>

### 2b. Data acquisition (ETL)

**Accession:** <GSE######> · **Tier taken:** <N — 10x `.h5`, filtered>
**Download:** <N> files · <N> GB · ~<N> min

| GSM | Title (as deposited) | Condition | n | File |
| --- | --- | --- | --- | --- |
| GSM6612345 | `WT_rep1` | wild-type | 1 | `GSM6612345_WT1_filtered.h5` |

- **Files not used:** <raw matrices, unrelated assays — and why>
- **Sample mapping source:** <GEO `characteristics_ch1` / Supplementary Table N / **`missing`**>
- **n per group vs the paper:** <matches Fig. 2 legend / **discrepancy: paper says 3 KO, series has 2**>

See `output/<name>.<ipynb|Rmd>` for the executable version.

### 2c. <Computational phase name — e.g. QC and filtering>

3. **<Step name>** — `repo` *(`analysis/qc.R:L22-38`)*
   - <Exact parameters and the invocation>
   - **Checkpoint:** paper reports <N> cells retained
4. **<Step name>** — `stated` *(Supplementary Methods, p.<N>)*
   - <Parameters>

---

## 3. What to expect when you run it

- **Should match closely:** <cell counts after QC, cluster count, top markers>
- **Will differ:** <UMAP coordinates always differ; DE p-values shift with
  package version; cluster numbering is arbitrary and rarely matches the paper's>
- **Watch for:** <the step most likely to fail first, and how it will look>

Re-running the authors' analysis on the authors' data is reproduction, not
replication. A modest numerical discrepancy is not evidence of an error in
either direction — a *sign flip* or a missing cluster is.

---

## 4. Documentation gaps

The substance of this report. Ranked by whether it blocks reproduction — the
four kinds have different remedies, so they stay separate.

### 4a. Blocking — reproduction cannot proceed as written
- **<gap>** — <what is missing, and what it blocks>.
  *Remedy:* <email the corresponding author for X / dbGaP application phs######
  (~<N> weeks) / regenerate from Tier 6 at ~<N> GB and <N> h>.

### 4b. Undocumented parameters — filled by inference
| Step | Missing | Value used | Basis |
| --- | --- | --- | --- |
| QC | mito % cutoff | 10% | **[inferred]** — field-standard for this tissue; paper states only "cells with high mitochondrial content were removed" |

### 4c. Undocumented steps — breaks in the chain
- <Where the prose jumps, what plausibly happened in between, and whether the
  repo covers it>

### 4d. Inaccessible assets
- <Repo 404s / accession embargoed until <date> / cell line not shared>.
  *Exact barrier and route:* <...>

### What the authors documented well
<Not filler — it tells the reader this reproduction is low-risk. e.g. "a
committed `renv.lock`, per-sample filtered `.h5` files, and a supplementary
sample table with genotype and batch. The environment and ETL sections above are
`stated` throughout because of it.">

---

## 5. Next steps
- <Concrete action — "run cells 1–6, confirm 12,483 cells, then compare to Fig. 2b">
- <Concrete action — "email <author> for the mito cutoff and clustering resolution">
- <Concrete action — "if extending to the lab's own samples, note the reference
  build differs and re-quantify">

---

*Generated by the paper reproduction agent. Steps are tiered `stated`, `repo`,
**[inferred]**, or `missing` — inferences are the report's, not the authors'. No
data files were downloaded; the notebook ships unrun. Corrections welcome.*
