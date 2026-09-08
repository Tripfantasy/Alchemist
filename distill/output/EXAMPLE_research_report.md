# Choosing a batch-correction method for multi-site single-cell studies

⚠️ **Synthetic example.** Every finding, number and citation below is fabricated. No source in the list resolves, and none should be quoted or relied on. This file exists to show the report format — the TL;DR, the evidence table with explicit confidence, the contested section, and recommendations tied back to numbered findings. A real report from this agent cites only sources it actually retrieved.

**Date:** 2026-09-08 · **Audience:** lab computational staff · **Depth:** Standard

## Question

Which batch-correction method should a lab standardize on for single-cell RNA-seq
collected across multiple sites — and does the choice change when the biological
signal of interest is subtle? Informs a decision about the lab's default pipeline.

## TL;DR

- **No method wins outright.** The ranking flips depending on whether batch and
  biological condition are confounded [1][4].
- For **unconfounded** designs, the three leading methods are within noise of one
  another; pick on runtime and maintenance, not accuracy [2].
- For **confounded** designs — the common case in multi-site work — aggressive
  correction removes real biological signal along with batch effect [4][7].
- **Standardize on a default, not a mandate.** The evidence supports one default
  with a documented escape hatch for confounded designs [1][6].
- The single highest-value change is not the method but **recording batch
  structure at collection time** [8].

## Scope

- **Covered:** integration methods for scRNA-seq, 2019–2025, human and mouse;
  benchmark studies with ≥3 datasets
- **Excluded:** spatial and multiome integration; methods without a maintained
  implementation
- **Assumptions:** "multi-site" means ≥2 collection sites with independent
  library prep; not merely multiple sequencing runs
- **Sources:** 8 total (6 peer-reviewed, 1 preprint, 1 benchmark repository) ·
  window: 2019–2025

## Findings

### How much does method choice actually matter?

- Across 12 benchmark datasets, the top three methods differed by <4% on
  batch-mixing metrics — smaller than the spread from parameter choice within a
  single method [2]
- Runtime differed by ~40× across the same methods, which matters more in
  practice than the accuracy gap [2]
- *Single-sourced:* one group reports a larger gap on very large datasets [9]

### What happens when batch and condition are confounded?

- Correction strength that is appropriate for unconfounded data removed 30–60%
  of true differential expression when condition was fully confounded with site [4]
- The effect is monotonic in correction strength — there is no setting that
  removes batch effect without touching confounded biology [4][7]
- No benchmark in this set evaluates partial confounding, which is the realistic
  middle case [gap — see below]

### Does the biological signal's magnitude change the answer?

- For large effects (whole-cell-type shifts), method choice was near-irrelevant [2][3]
- For subtle effects (within-cell-type state changes), methods diverged sharply,
  and the most aggressive method performed worst [4]

## Evidence Summary

| Claim | Support | Strongest source | Confidence |
|---|---|---|---|
| Top methods are within noise when unconfounded | 2 benchmarks, 12 datasets | [2] | High |
| Aggressive correction destroys confounded signal | 1 benchmark, 1 simulation | [4] | Moderate |
| Runtime gap exceeds accuracy gap | 1 benchmark | [2] | Moderate |
| Method choice matters more for subtle effects | 1 benchmark, 1 reanalysis | [4] | Low |

Confidence levels follow `resources/source-quality.md`.

## Contested & Uncertain

- **Whether batch-mixing metrics measure the right thing** — one group argues
  they reward over-correction by construction [7]; the benchmark authors argue
  paired biological-conservation metrics already control for this [2].
  Unresolved because the two camps use different ground-truth definitions.
- **Whether deep-learning methods generalize** — strong in-benchmark results [9]
  versus reported failures on out-of-distribution tissue [5]. Too few
  independent replications to call.

## Gaps

- **Partial confounding is unevaluated.** Every benchmark here uses either fully
  confounded or fully crossed designs; real studies sit in between.
- **No study reports cost of being wrong** — i.e. downstream false-discovery
  consequences of over-correction.
- A search for prospective (rather than retrospective) evaluations returned
  nothing. Absence worth noting: this literature is entirely reanalysis.

## Recommendations & Next Steps

**Recommendations**

- **Adopt one default method for unconfounded designs, chosen on runtime and
  maintenance** — because accuracy differences are within noise [2].
  Confidence: High.
- **Require an explicit review when batch and condition are confounded** — do not
  apply the default; the failure mode is silent loss of real signal [4][7].
  Confidence: Moderate.
- **Avoid selecting a method on benchmark leaderboards alone** — the metrics
  themselves are contested [7]. Confidence: Moderate.
- **Do not standardize on a deep-learning method yet** — generalization evidence
  is thin and contested [5][9]. Confidence: Low; revisit if independent
  out-of-distribution replications appear.

**Next steps**

| # | Action | Why | Effort |
|---|---|---|---|
| 1 | Add batch/site fields to the intake sheet | Closes the highest-value gap [8]; makes confounding visible before analysis | Low |
| 2 | Run the two candidate defaults on one in-house dataset | Converts a literature call into a local one | Med |
| 3 | Write the confounded-design escape hatch into the pipeline docs | Makes recommendation 2 enforceable | Low |

## Sources

1. Example, A., & Placeholder, B. (2023). *A fabricated review of integration strategies*. Journal of Example Methods. [synthetic — does not exist]
2. Sample, C. et al. (2022). *A fabricated benchmark of twelve datasets*. Journal of Example Methods. [synthetic — does not exist]
3. Demo, D. (2021). *A fabricated reanalysis*. Example Reports. [synthetic — does not exist]
4. Placeholder, B. et al. (2024). *A fabricated study of confounded designs*. Example Genomics. [synthetic — does not exist]
5. Fictional, E., & Demo, D. (2025). *A fabricated out-of-distribution evaluation*. Example Letters. [synthetic — does not exist]
6. Example, A. (2020). *Fabricated pipeline guidance*. Example Practice. [synthetic — does not exist]
7. Sample, C. (2023). *A fabricated critique of mixing metrics*. Example Commentary. [synthetic — does not exist]
8. Demo, D. et al. (2024). *Fabricated recommendations on study design capture*. Example Design. [synthetic — does not exist]
9. Fictional, E. et al. (2024). *A fabricated deep-learning benchmark* [preprint]. Example Preprints. [synthetic — does not exist]
