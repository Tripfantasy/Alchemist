# Reproduction Protocol — cortical organoid snRNA-seq, Fig. 2

⚠️ **Synthetic example.** The paper, DOI, accession, repository and every number below are fabricated. Nothing here describes real work, and no citation resolves. It exists to show the report format — above all the provenance tiers, which are the point of this agent.

**Paper:** Example, A. et al. (2024), *Journal of Example Neuroscience*. doi:10.0000/example.2024.0001
**Requested by:** example user · **Date:** 2026-09-08
**Scope:** computational · **Target:** Fig. 2 — cell-type clustering of cortical organoids
**Data:** GSE000000 (fabricated) · **Code:** `github.com/example-lab/example-repo` (fabricated)

**Goal as understood:**
> Reproduce the clustering and cell-type assignment shown in Fig. 2b–d from the
> deposited processed matrices. Wet-lab derivation of the organoids is out of scope.

---

## 0. Reproducibility at a glance

| | Status |
| --- | --- |
| Processed data deposited | yes — Tier 2 filtered `.h5` per sample |
| Authors' code available | partial — clustering yes, cell-type assignment no |
| Environment pinned | versions in text only; no lockfile |
| Sample→condition mapping | GEO `characteristics_ch1` |
| **Verdict** | reproducible with inferences — see §4b |

**Provenance tiers used below:** `stated` (in the paper) · `repo` (in the
authors' code) · **[inferred]** (supplied by this report) · `missing`
(unrecoverable). Every step carries one.

⚠️ Steps 5–6 are **[inferred]**. The paper gives no mitochondrial cutoff and no clustering resolution, so cluster counts will not match Fig. 2b exactly. Expect the same major populations in different proportions, and arbitrary cluster numbering.

---

## 1. Environment

**Stack:** Python 3.11 · **Source:** paper text; no lockfile deposited

| Package | Version | Source |
| --- | --- | --- |
| `scanpy` | 1.10.1 | Methods, "Single-nucleus analysis" |
| `anndata` | unstated | **[inferred]** — whatever `scanpy` 1.10.1 pins |
| `harmonypy` | unstated | **[inferred]** — paper names Harmony, not a version |
| `leidenalg` | unstated | **[inferred]** — required by the stated `leiden` call |

**Reference:** GRCh38-2020-A · **Annotation:** GENCODE v32 — both `stated` (Methods)
**Recommended resources:** 8 cores · 64 GB RAM · 40 GB disk · ~2 h wall-clock
**Setup:**

```bash
python3 -m venv .venv && ./.venv/bin/pip install "scanpy==1.10.1" harmonypy leidenalg
```

⚠️ Three of four package versions are inferred. Pin them yourself before treating any numerical result as a match — an unpinned `scanpy` minor bump has changed default HVG behaviour before.

---

## 2. Protocol

### 2b. Data acquisition (ETL)

**Accession:** GSE000000 · **Tier taken:** 2 — 10x filtered `.h5`
**Download:** 6 files · 4.2 GB · ~8 min

| GSM | Title (as deposited) | Condition | n | File |
| --- | --- | --- | --- | --- |
| GSM0000001 | `CTRL_rep1` | control | 1 | `GSM0000001_CTRL1_filtered.h5` |
| GSM0000002 | `CTRL_rep2` | control | 1 | `GSM0000002_CTRL2_filtered.h5` |
| GSM0000003 | `CTRL_rep3` | control | 1 | `GSM0000003_CTRL3_filtered.h5` |
| GSM0000004 | `MUT_rep1` | mutant | 1 | `GSM0000004_MUT1_filtered.h5` |
| GSM0000005 | `MUT_rep2` | mutant | 1 | `GSM0000005_MUT2_filtered.h5` |
| GSM0000006 | `MUT_rep3` | mutant | 1 | `GSM0000006_MUT3_filtered.h5` |

- **Files not used:** raw unfiltered matrices (Tier 4) — the filtered set is what
  Fig. 2 was built from, per Methods.
- **Sample mapping source:** GEO `characteristics_ch1`
- **n per group vs the paper:** matches the Fig. 2 legend (3 control, 3 mutant)

See `output/EXAMPLE_notebook.ipynb` for the executable version.

### 2c. QC, integration and clustering

1. **Load per-sample matrices** — `repo` *(`analysis/load.py:L14-31`)*
   - `sc.read_10x_h5()` per GSM, concatenated with `sample` in `.obs`
2. **Filter cells by gene count** — `stated` *(Methods, "Quality control")*
   - Retain cells with 200 ≤ `n_genes_by_counts` ≤ 6000
   - **Checkpoint:** paper reports 41,782 nuclei retained across all samples
3. **Filter genes** — `stated` *(Methods, "Quality control")*
   - Retain genes detected in ≥ 3 cells
4. **Normalize and log-transform** — `repo` *(`analysis/qc.py:L40-44`)*
   - `normalize_total(target_sum=1e4)`, then `log1p`
5. **Filter by mitochondrial fraction** — **[inferred]**
   - Cutoff used here: **10%**. The paper states only that "nuclei with high
     mitochondrial content were removed" and gives no threshold; the repo does
     not perform this step. 10% is a common default for nuclei preparations —
     it is this report's choice, not the authors'.
6. **Cluster** — **[inferred]**
   - Leiden at **resolution 1.0**. The paper names Leiden and reports 14
     clusters but never gives a resolution; the repo's clustering script is
     absent. Resolution 1.0 is the `scanpy` default and is unlikely to
     reproduce exactly 14 clusters.
   - **Checkpoint:** paper reports 14 clusters
7. **Assign cell types** — `missing`
   - The paper says assignments were "curated manually against canonical
     markers" and lists no marker panel. The repo contains no assignment code.
     This step cannot be reproduced; §4a covers the remedy.

---

## 3. What to expect when you run it

- **Should match closely:** nuclei retained after steps 2–3, the major
  excitatory/inhibitory/glial split, top markers per major population
- **Will differ:** UMAP coordinates (always), exact cluster count (step 6 is
  inferred), cluster numbering (arbitrary), DE p-values (version-sensitive)
- **Watch for:** step 5 failing loudly if `.var` lacks a mitochondrial prefix —
  the deposited matrices use `MT-`, not `mt-`

Re-running the authors' analysis on the authors' data is reproduction, not
replication. A modest numerical discrepancy is not evidence of an error in
either direction — a *sign flip* or a missing cluster is.

---

## 4. Documentation gaps

### 4a. Blocking — reproduction cannot proceed as written
- **Cell-type assignment (step 7)** — no marker panel, no assignment code. Fig.
  2c/2d cannot be regenerated as published.
  *Remedy:* email the corresponding author for the marker table, or substitute a
  published reference-based classifier and report the substitution prominently.

### 4b. Undocumented parameters — filled by inference
| Step | Missing | Value used | Basis |
| --- | --- | --- | --- |
| 5 | mitochondrial % cutoff | 10% | **[inferred]** — field default for nuclei; paper says only "high mitochondrial content was removed" |
| 6 | Leiden resolution | 1.0 | **[inferred]** — `scanpy` default; paper reports 14 clusters but no resolution |
| 1 | `anndata`, `harmonypy`, `leidenalg` versions | latest compatible | **[inferred]** — paper names methods, not versions |

### 4c. Undocumented steps — breaks in the chain
- Methods jump from normalization straight to "clusters were identified".
  Highly-variable-gene selection, scaling and PCA are all implied but never
  described, and the repo covers only the first of the three.

### 4d. Inaccessible assets
- None. The accession is public and the repository resolves.

### What the authors documented well
Per-sample filtered `.h5` files, a complete `characteristics_ch1` mapping with
genotype and batch, an explicit reference build and annotation version, and
loading code that runs unmodified. The ETL section above is `stated` or `repo`
throughout because of it — which is why the gaps concentrate in one place
(clustering) rather than being spread through the whole pipeline.

---

## 5. Next steps
- Run cells 1–4, confirm nuclei retained against the Methods figure, then stop
  and compare before proceeding past the inferred steps.
- Email the corresponding author for the mitochondrial cutoff, clustering
  resolution, and marker panel — three short answers unblock §4a and §4b entirely.
- If extending to your own samples, note the GRCh38-2020-A reference and
  re-quantify rather than merging count matrices across builds.

---

*Generated by the paper reproduction agent. Steps are tiered `stated`, `repo`,
**[inferred]**, or `missing` — inferences are the report's, not the authors'. No
data files were downloaded; the notebook ships unrun. Corrections welcome.*
