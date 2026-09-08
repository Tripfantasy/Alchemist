# Documentation Gap Checklist

Audit Phase 5 against this list, not against whatever you happen to notice.
These are the details papers routinely omit — each has broken a real
reproduction attempt.

**How to use it:** walk the relevant sections, mark each item `stated`, `repo`,
`inferred`, or `missing`. Anything not `stated`/`repo` belongs in the report's
gap section. Do not report an item as a gap without checking the supplement and
the repo first — most "missing" parameters are in one of them.

---

## Computational — highest-frequency omissions

Roughly in order of how often they're missing *and* how much they change results.

- [ ] **Software versions.** "Seurat" without a version is not reproducible —
      v4→v5 changed default normalization and the assay class. Same for scanpy,
      CellRanger, STAR, Salmon.
- [ ] **Reference genome + annotation build.** `mm10` vs `GRCm39`, GENCODE
      vM25 vs vM33. Changes gene sets, and therefore every downstream count.
- [ ] **Random seeds.** Absent almost always. Affects UMAP layout, Leiden/Louvain
      partitions, and any subsampling. Cluster *count* can change.
- [ ] **Clustering resolution.** The most common single omission in scRNA-seq
      papers, and it directly sets the cluster count the paper reports.
- [ ] **QC thresholds.** min genes/cell, min cells/gene, max mito %, max
      counts. "Low-quality cells were removed" is not a threshold.
- [ ] **Doublet handling.** Whether at all, which tool, expected rate.
- [ ] **Ambient RNA correction.** SoupX/CellBender, and the contamination
      estimate used.
- [ ] **Normalization details.** Target sum / scale factor, log base,
      regressed-out covariates, whether scaling was per-batch.
- [ ] **HVG selection.** Count, method (`seurat_v3` vs `cell_ranger`),
      per-batch or global.
- [ ] **Dimensionality.** Number of PCs carried into the neighbor graph. How it
      was chosen (elbow, JackStraw, arbitrary).
- [ ] **Batch correction.** Method, which variable, and whether the corrected
      embedding was used for DE (it should not be).
- [ ] **DE method and design.** Wilcoxon vs MAST vs pseudobulk-DESeq2; whether
      replicate structure was respected. Cell-level tests on n=3 mice inflate
      significance — if the paper did this, say so, because it changes how the
      result should be read.
- [ ] **Multiple-testing correction** and the significance cutoff, including
      any log-fold-change threshold applied alongside it.
- [ ] **Cell-type annotation basis.** Manual on which markers, or a reference
      dataset — which one, which version.
- [ ] **Filtered vs raw matrices**, and the cell-calling threshold.
- [ ] **Enrichment specifics.** Database + version, the background gene set
      (frequently wrong and rarely stated), the ranking statistic.
- [ ] **Sample→condition mapping** for deposited data. Blocking when missing.
- [ ] **Which samples were excluded**, and why. A series with more samples than
      the paper analyzes always means something.
- [ ] **Compute footprint.** Not needed for correctness, needed for planning.

## Wet-lab — highest-frequency omissions

- [ ] **Catalog numbers** for antibodies and key reagents. Clone matters as much
      as target; two anti-GFAP antibodies are not interchangeable.
- [ ] **Antibody dilutions** and incubation time/temperature.
- [ ] **Animal details.** Strain *with substrain* (`C57BL/6J` vs `C57BL/6N`
      differ phenotypically), sex, exact age, n per group, littermate controls.
- [ ] **Centrifugation in `g`, with rotor** — RPM alone is unreproducible.
- [ ] **Enzyme lot/activity** for dissociation, and digestion time. The most
      common source of cell-composition differences in scRNA-seq.
- [ ] **Fixation and permeabilization** specifics.
- [ ] **Buffer recipes**, especially "our standard buffer".
- [ ] **Timing dependencies.** What is prepped a day ahead, what cannot pause.
- [ ] **Perfusion/dissection detail** — anatomical boundaries of a dissected
      region. "Cortex" spans very different tissue between labs.
- [ ] **Blinding and randomization.** Usually only in the Reporting Summary.
- [ ] **Instrument settings** — cycler programs, microscope objective/NA/laser
      power/exposure, flow cytometer voltages.
- [ ] **"As previously described [17]"** — the step is outsourced. Follow the
      citation. If unreachable, the step is `missing`, not `stated`.

## Assets and access

- [ ] Accession resolves and is public (not embargoed, not mistyped)
- [ ] Sample count matches the paper
- [ ] Repo URL resolves, is non-empty, and covers the target figure
- [ ] Lockfile or `sessionInfo()` present
- [ ] Intermediate objects deposited, or must be regenerated
- [ ] Controlled-access components identified, with the application route
- [ ] Plasmids/cell lines/mouse lines deposited (Addgene, JAX, repository) or
      "available on request" — the latter is a gap, not availability
- [ ] Custom code for a custom instrument — usually unpublished
- [ ] Repo license, if code will be lifted into the deliverable

---

## Reporting rules

- **Name the specific parameter.** "Methods are incomplete" tells the researcher
  nothing. "No mito % cutoff given; 10% assumed, which will change the cell
  count in Fig. 2b" is actionable.
- **Rank by blocking.** A missing centrifuge speed is a nuisance; an undeposited
  count matrix is fatal. Never flatten them into one list.
- **Distinguish "the authors omitted it" from "I couldn't find it."** If the
  supplement was paywalled or unfetchable, that is a limitation of this run, and
  it must be labeled as such rather than blamed on the paper.
- **Credit good documentation.** A deposited lockfile and processed matrices
  mean low reproduction risk. Saying so is the honest counterpart to the
  criticism, and it is what tells the researcher this is worth their week.
- **Standard practice is not documentation.** A field-standard default is a
  reasonable inference and still a gap — the paper's result depends on a number
  the paper never gave.

## Recurring patterns

Append when the same omission shows up across papers from one lab, journal, or
method — it makes the next audit faster.

- *(none recorded yet)*
