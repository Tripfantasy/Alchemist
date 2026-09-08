# Workflow: Paper Reproduction

**Purpose:** Take a published paper and turn it into something a researcher can
actually run — a step-by-step protocol for the bench work, a documented notebook
for the computational analysis, or both — plus an honest account of what the
paper does not document well enough to reproduce.

**Invoke with:** `/brew <paper URL, DOI, or path to PDF>` — or say
"reproduce the analysis in <paper>" and the `paper-reproduction` skill triggers.

**Inputs:** a paper (URL, DOI, PMID, or local `.pdf`) and the user's goal.
**Outputs:**

- `output/<first-author><year>_<topic>_protocol.md` **and** `.pdf` — the report
- `output/<first-author><year>_<topic>.ipynb` or `.Rmd` — the runnable notebook,
  when the request involves computational analysis

This workflow inherits `CLAUDE.md` — ask before starting, show the plan, bullets
over paragraphs, output to `output/`, every report ships as both `.md` and
`.pdf`. Don't restate those rules; follow them.

**Tool note:** every tool this workflow needs is deferred — load schemas with
`ToolSearch` before calling. Local PDFs are read with the `Read` tool (`pages`
parameter — required above 10 pages, 20 pages max per call).

The **PubMed / bioRxiv / Scite connectors are authorized and working** (verified
2026-09-08). Prefer them over the open web, in this order:

| Source | Load with | Use it for |
| --- | --- | --- |
| Local PDF + supplements | `Read` | Richest source when the user has one — supplementary methods especially |
| **Scite** | `select:mcp__claude_ai_Scite__search_literature,mcp__claude_ai_Scite__read_fulltext` | Targeted full-text passages: pass `dois` **plus** a `term`, once per method section. Also `editorialNotices` and a paywall `access` link |
| **PubMed** | `select:mcp__claude_ai_PubMed__search_articles,mcp__claude_ai_PubMed__convert_article_ids,mcp__claude_ai_PubMed__get_full_text_article` | Resolving a citation → PMID → PMCID → PMC full text. Cite PubMed + the DOI wherever you use its content |
| **bioRxiv** | `select:mcp__claude_ai_bioRxiv__get_preprint` | Preprints, **by DOI** — `search_preprints` has no keyword search (date + category only) and cannot find a named preprint |
| `WebSearch` / `WebFetch` | `select:WebSearch,WebFetch` | Fallback, and the only route to a GitHub repo or a publisher page the connectors don't index |

Two things the connectors do *not* change:

- **Retraction check is now mandatory.** Scite returns `editorialNotices`; read
  them before building a protocol. A retracted or corrected paper goes in the
  report's Scope section, at the top, in an ⚠️ box.
- **A connector excerpt is still just a source.** It feeds `stated` only for
  what it literally says, and it never substitutes for fetching a repo file
  (Phase 2) or probing an accession (`workflows/etl_geo.md`).

---

## The rule that governs everything below

**Every step you write carries a provenance tier, and the tiers never blur.**
A protocol that silently mixes what the authors wrote with what you assumed is
worse than no protocol — the researcher cannot tell which parts to trust.

| Tier | Means | How it appears in the deliverable |
| --- | --- | --- |
| `stated` | Explicit in the paper or its supplement | Cite the section: *(Methods, "Library prep")* |
| `repo` | Read out of the authors' own code | Cite `file.py:L40-58` |
| `inferred` | Tool default or field-standard practice you supplied | Marked **[inferred]** inline, with what you assumed |
| `missing` | Not recoverable from any available source | Listed in the gap section, never silently filled |

Two failure modes to guard against, in order of severity:

1. **Laundering an inference into a fact.** "Cells were clustered at resolution
   0.5" when the paper never said 0.5 is fabrication, however plausible 0.5 is.
   Write it as **[inferred — paper gives no resolution; 0.5 is the Seurat
   default]**.
2. **Filling a `missing` step with silence.** A protocol that skips from
   dissociation to library prep because the paper omitted the intervening step
   reads as though no step exists. Say "the paper does not state X" explicitly.

---

## Phase 0 — Read first, then ask

### 0a. Skim before asking anything

Intake questions written without reading the paper are generic, and generic
options waste the round. Spend one pass on:

- **Abstract + figure titles** — what was actually done, and what each figure claims
- **Methods section headings** — the real structure of the work, and whether it
  is wet-lab heavy, computational heavy, or genuinely both
- **Data Availability / Code Availability statements** — accessions and repo
  URLs. These two paragraphs determine whether reproduction is even possible.
- **Supplementary file list** — supplementary methods routinely hold the
  parameters the main text omits

Don't extract details yet. This pass exists to make the questions specific.

### 0b. One batched intake round

Ask **3–4 questions in a single `AskUserQuestion` call**, then start working.
No second round, no follow-up trickle. Every option must name something from
*this paper* — a specific figure, assay, or dataset — not an abstract category.

| # | Header | What it establishes |
| --- | --- | --- |
| 1 | `Scope` | Wet-lab protocol, computational reproduction, or both |
| 2 | `Target` | **Which figure or analysis.** Name the paper's actual figures |
| 3 | `Depth` | Orientation, runnable reproduction, or extension to new data |
| 4 | `Data` | Which accession/sample subset, when the paper has several |

**Bad** (generic — could attach to any paper):
> What kind of analysis do you want?
> - Overview · Detailed · Full reproduction

**Good** (a paper with scRNA-seq + patch-clamp + a mouse model):
> Which part of this paper do you want to reproduce?
> - **Fig. 2 snRNA-seq clustering** — GSE214xxx, 10x, 6 samples, `.h5` available
> - **Fig. 4 DE + GO enrichment** — depends on Fig. 2 output; authors' repo has the script
> - **Fig. 5 patch-clamp** — wet-lab only, no deposited data
> - **The mouse crossing + tamoxifen induction** — bench protocol, 8-week timeline

Question 2 is the one that makes the deliverable useful. A paper has 6 figures
and a researcher wants one of them; reproducing all six produces a document
nobody runs.

**Intake rules:**

- One round. If something stays ambiguous, assume, state the assumption in the
  report's Scope section, and keep going.
- Drop a slot the request already answered. A two-question round is fine.
- "Other" free text outranks the options you offered.
- Carry the answers into the report's Scope section close to verbatim.

### 0c. Show the plan

```
Reproducing: <short citation>
Scope: <wet-lab | computational | both>  ·  Target: <figure/analysis>
Data: <accessions>  ·  Code: <repo URL or "none found">
Deliverables: output/<name>_protocol.md + .pdf<, output/<name>.ipynb|.Rmd>

Steps: 1 <...>  2 <...>  3 <...>
```

Transparency, not an approval gate. Proceed unless the user interjects.

---

## Phase 1 — Extract the method

Work through every source of detail, in this order. Later sources routinely
contradict earlier ones — when they do, **the code wins over the prose**, and
say in the report that they disagreed.

1. **Main Methods** — the skeleton
2. **Supplementary Methods / Reporting Summary** — where parameters live. The
   Life Sciences Reporting Summary is often the only place antibody catalog
   numbers, software versions, and replicate counts appear.
3. **Figure legends** — n per group, statistical test, significance thresholds
4. **The authors' repository** — actual parameters, actual versions (Phase 2)
5. **Cited protocol papers** — a Methods section that says "as previously
   described [17]" has outsourced the step. Follow the citation: resolve it with
   `lookup_article_by_citation` or `search_articles`, then pull the text via
   `convert_article_ids` → `get_full_text_article`, or Scite with that DOI and a
   `term` for the step. This is the connectors' biggest single win — the chain
   is now usually followable. A step recovered this way is `stated`, but **cite
   the paper it actually came from**, not the paper you are reproducing. If the
   chain still dead-ends (paywalled, or a citation to a book/thesis), the step
   is `missing` — say which citation you could not reach.

Build the step list in the **session scratchpad**, not in `output/`. One row per
step:

```
step | tier | source (section / file:line) | parameters | what's unstated
```

### For wet-lab steps, capture

- Reagents with vendor + catalog number, and concentrations
- Volumes, temperatures, durations, centrifuge speeds (with units — `g`, not RPM,
  or state the rotor)
- Animal/sample details: strain, sex, age, n per group, housing, IACUC/IRB
  approval where cited
- Sequential dependency: what must be prepped a day ahead
- Equipment that gates the protocol at all (a specific instrument, a cryostat)

### For computational steps, capture

- Tool + **exact version**, and the invocation with all non-default parameters
- Reference genome/annotation build (`GRCm39` vs `mm10` changes downstream results)
- Filtering thresholds: min genes/cell, max mito %, doublet handling
- Normalization, HVG selection, dimensionality, batch-correction method
- Random seeds, and clustering resolution
- Statistical test, multiple-testing correction, and the significance cutoff
- Compute footprint: cores, RAM, wall-clock, GPU if any

Anything on those lists the paper omits goes in the gap section. Do not fill it
from your own preferences without marking it `[inferred]`.

---

## Phase 2 — Find the code and the data

### Code

Look in this order: Code Availability statement → Data Availability statement →
main-text footnotes → the corresponding author's GitHub org → a
`WebSearch` for `<first author> <year> github <topic>`.

Then **verify what you found**:

- Fetch the repo's README and file listing. A repo URL in a paper is not proof
  of a working repo — 404s, empty repos, and "code available on request" are
  routine.
- Note the **language and stack** — it decides the deliverable format (see
  Phase 4) and it tells you which package manager the environment section needs.
- Check for `environment.yml`, `requirements.txt`, `renv.lock`, `sessionInfo()`
  output, or a Dockerfile. A lockfile is the single most valuable artifact in
  the repo — it makes the environment section `stated` instead of `inferred`.
- Read the scripts that produce the **target figure**, not the whole repo. Map
  script → figure where you can.
- Check for Zenodo DOIs — authors often deposit a frozen snapshot with
  intermediate objects the GitHub repo lacks.

**Never cite a repo file you have not fetched.** A parameter attributed to
`analysis/cluster.R:L30` that isn't there is the same failure as a fabricated
citation.

### Data

Accessions to expect, and what each one is:

- **GEO** `GSE######` — series; `GSM######` per sample. Processed matrices live
  in the series `suppl/` directory. **The preferred source.**
- **SRA** `SRP######` / `PRJNA######` — raw reads only. Last resort.
- **ArrayExpress** `E-MTAB-####`, **dbGaP** `phs######` (controlled access —
  flag the application requirement), **Zenodo/figshare** DOIs, **Synapse**
  `syn#####` (registration required), **EMPIAR/PRIDE** for EM/proteomics.

Then follow `workflows/etl_geo.md` — it covers accession probing, the file-format
preference ladder, and loader code. Do not improvise the ETL step from memory.

---

## Phase 3 — Confirm the reproduction target

Before writing anything, state back: the figure/analysis, the accession and
sample subset, the stack, the deliverable format, and what you expect to be
unreproducible. A misread target wastes the whole deliverable.

Also state plainly, once, what "reproduction" means here:

> Re-running the authors' analysis on the authors' data. Cluster counts, DE
> gene lists, and p-values will land close to the paper but rarely identically
> — package versions, random seeds, and reference builds all move numbers.
> A discrepancy is not automatically an error in either direction.

---

## Phase 4 — Write the deliverables

### 4a. The protocol report

Fill `resources/protocol_report_template.md`. Get the date from `date +%F` — never
guess it. Filename: `output/<first-author><year>_<topic>_protocol.md`.

- Number every step. A researcher works down the list at a bench or a terminal.
- Tier every step per the table at the top of this file.
- Keep bullets over paragraphs (`CLAUDE.md`).
- For computational scope, include the **Environment** section: packages with
  versions, reference genome build, and recommended cores/RAM/disk/wall-clock.
- Two renderer conventions: consecutive `**Label:** value` field lines each keep
  their own line, and **a paragraph opening with ⚠️ renders as an amber caveat
  box** — use it for inferred steps and controlled-access data.

Then render the PDF:

```bash
./.venv/bin/python scripts/render_report.py output/<name>_protocol.md
```

The `.md` is the source of truth; re-run the renderer after any edit. Never
hand-edit a `.pdf`.

### 4b. The notebook

Only when the scope includes computational analysis.

**Format mirrors the paper's own stack** — `.ipynb` if the authors worked in
Python/scanpy, `.Rmd` if they worked in R/Seurat/Bioconductor. Code lifts across
directly that way, and a reader comparing your notebook to the repo sees the same
idioms. If the repo is mixed, follow the stack that produced the *target figure*.
If there is no repo at all, choose from the paper's named tools; if those are
Python-shaped use `.ipynb`, otherwise `.Rmd`. State the choice and why.

Build it with the scaffolder rather than hand-writing notebook JSON:

```bash
./.venv/bin/python scripts/make_notebook.py spec.json --out output/<name>.ipynb
```

Follow `resources/notebook_scaffold.md` for section order and conventions. The
essentials:

- **Runs top to bottom on a clean machine.** No hidden state, no cell that
  depends on something run out of order.
- **Cell 1 is environment**, cell 2 is config (accession, paths, thresholds as
  named variables at the top — never buried in a later cell).
- **Every step's markdown cell names its tier and source**, same as the report.
  An `[inferred]` parameter is called out where the researcher will change it.
- **ETL first, and idempotent** — re-running must not re-download.
- Paper-reported checkpoints inline: "the paper reports 12,483 cells after
  filtering; this cell prints the count you got."
- **Never write code you have not reasoned through against the actual data
  structure.** Guessing at column names in an unfetched matrix produces a
  notebook that fails on cell 3.

⚠️ This project does **not** download data or execute the analysis. The notebook
ships unrun, with the accession and paths wired in. Say so in the handoff, and
list the first command the user should run.

---

## Phase 5 — The gap audit

This is the half researchers actually need, not an appendix. Read
`resources/method_gaps.md` and work its checklist — it lists the details papers
routinely omit, so you audit against a standard rather than against whatever you
happen to notice.

Separate four kinds of missing, because the remedies differ:

| Gap | Means | Remedy |
| --- | --- | --- |
| **Undocumented parameter** | The step is named, a value is not | Email the authors; or `[inferred]` with the default stated |
| **Undocumented step** | The prose jumps; something happened in between | Reconstruct from the repo, or flag as a break in the chain |
| **Inaccessible asset** | Repo 404s, accession embargoed, dbGaP-controlled | Name the exact barrier and the application route |
| **Structurally unreproducible** | No data deposited, custom hardware, a reagent that no longer exists, a cell line not shared | Say what new work the question would require |

Rules for this section:

- **Be specific.** "Methods are incomplete" is useless. "The paper gives no mito
  % cutoff, and the repo's `qc.R` is not the version that produced Fig. 2 —
  cluster counts will not match exactly" is actionable.
- **Rank by whether it blocks reproduction.** A missing centrifuge speed is a
  nuisance; an undeposited count matrix is fatal. Don't flatten them into one list.
- **Credit good documentation.** If the authors deposited a lockfile and
  processed matrices, say so — it tells the researcher this reproduction is
  low-risk, and it is the honest counterpart to the criticism.
- **Never conclude "the data doesn't exist" from one source.** An accession
  absent from the Data Availability statement may still appear in a figure
  legend, a supplementary table, or the repo README. Check before declaring it.

---

## Phase 6 — Self-check, then hand off

- [ ] Every step tiered, and no `inferred` step dressed as `stated`?
- [ ] Every repo file and accession cited actually fetched and verified?
- [ ] Notebook runs top to bottom in principle — no out-of-order state, no
      guessed column names, config at the top?
- [ ] Environment section carries real versions, not "latest"?
- [ ] Gap section specific, ranked by blocking, and honest about what is fatal?
- [ ] Paper-reported checkpoint numbers included so the user can compare?
- [ ] Both `.md` and `.pdf` in `output/`, PDF regenerated after the last edit?
- [ ] Data files: none downloaded, nothing written outside `output/` and `data/`?

**Report back short** — do not paste the report into the terminal:

- File paths (`.md`, `.pdf`, notebook)
- 3–5 bullets: what the paper documents well, what it doesn't
- The single biggest reproduction risk
- The first command the user runs, and the expected download size
- Any retraction, correction, or editorial concern found on the paper — say
  "none found" when you checked and there were none, so the check is visible
- Which sources the method actually came from (PDF / Scite / PubMed / repo), and
  any section you could not reach through any of them

**Offer, don't auto-run:** publishing the protocol as a shareable Artifact page
for the department.

---

## Notes for maintaining this workflow

- Phase 0a (read before asking) is the highest-leverage step. A run that goes
  sideways almost always skipped it and asked generic questions.
- The provenance tiers are the whole credibility of the deliverable. If you
  find yourself wanting a fifth tier, you probably want `inferred` with a
  better note.
- Phase 5 is where generic filler creeps in ("methods could be more detailed").
  Check it hardest.
- If several papers from the same lab come through, their omissions repeat.
  Worth noting in `resources/method_gaps.md` when a pattern shows up.
