# Workflow: Data Discovery

Given a researcher's project description and goals, produce a manifest of
existing files that serve those goals — and an honest account of what the goals
need that the data cannot supply.

**Hard rule, no exceptions:** this workflow is read-only on Globus. Never
transfer, rename, delete, or create anything on a collection.

Three layers enforce this. The binding one is the **collection permission**:
the confidential client holds `r` on the guest collection, so Globus rejects
writes server-side. The in-process guard in `scan_endpoint.py` is a backstop,
not the guarantee. Never work around either, and never suggest granting `rw`
"temporarily" — there is no task in this workflow that needs it.

Before the first scan against a new collection, run:

```bash
./.venv/bin/python scripts/verify_readonly.py <COLLECTION_UUID>
```

---

## Step 1 — Intake

Ask these before doing anything else. Do not proceed on assumptions.

**Always ask:**

1. **File types.** Which are useful here? Offer the groups from
   `resources/vocab.json` → `type_groups`: `neuroimaging`, `sequencing`,
   `omics`, `tabular`, `docs`, `code`. Accept explicit extensions too.
   *Why it matters:* raw `.fastq.gz` and a processed `.h5ad` answer completely
   different questions. A researcher who wants to re-cluster cells does not
   want 400 GB of reads.
2. **Folder scope.** One or more path prefixes, or the whole collection.
   *Why it matters:* a full walk of a large collection is slow and noisy.

**Ask when the goal is vague.** The test: could two different datasets both
plausibly satisfy this request? Then it is too vague. Typical gaps:

- **Organism / model** — mouse, human, organoid, paddlefish?
- **Tissue or region** — OE, OB, VNO, cortex, whole brain?
- **Modality** — bulk vs single-cell vs single-nucleus vs spatial vs imaging?
- **Comparison** — what is being contrasted? Genotype, age, condition, timepoint?
  A goal with no contrast usually means the researcher has not settled the design.
- **Developmental stage** — embryonic, postnatal day, adult?
- **Stage of processing** — raw reads to reprocess, or an analysis-ready matrix?

Ask at most 3–4 of these at once. Prefer the ones that would change which files
get returned.

## Step 2 — Confirm scope before scanning

State back: collection, roots, type filter, and the goal as you understood it.
A scan of a large tree is not free, and a misread goal wastes it.

## Step 3 — Scan (skip if a fresh inventory exists)

```bash
./.venv/bin/python scripts/scan_endpoint.py <COLLECTION_UUID> \
    --path / \
    --depth 5 \
    --out knowledge/inventory.jsonl
```

Reuse an existing `knowledge/inventory.jsonl` if it covers the requested roots
and is recent. Re-scan when the roots differ or the tree has changed. **A full
scan of this collection takes ~3 hours** — do not launch one casually.

`--depth 5` is the established setting: it reaches inside instrument session
folders without descending into per-trial subdirectories. Depth 8 was tried and
abandoned as impractical.

Scan WITHOUT `--types` so one inventory serves every future query; filter per
question in `search.py` instead.

Note `--types` here narrows the *walk*. To keep one broad inventory and filter
per query instead, scan without `--types` and pass it to `search.py`. Prefer
that when you expect several queries against the same tree.

## Step 4 — Index

```bash
./.venv/bin/python scripts/build_index.py --inventory knowledge/inventory.jsonl
```

Writes associations to `knowledge/file_associations.jsonl`, refreshes
`knowledge/ASSOCIATIONS.md`, and writes `knowledge/coverage.json`.

## Step 5 — Search

```bash
./.venv/bin/python scripts/search.py "<the researcher's goal, in their words>" \
    --types omics,tabular --folder /projects/yu/ \
    --limit 40 --out knowledge/candidates.json
```

This is a **recall device, not a judge**. It casts wide on token overlap. Your
job in the next step is to cut.

## Step 6 — Judge, then write the report

Read `knowledge/candidates.json` and apply real judgment. The score is lexical;
it does not know biology.

- **Drop false positives.** A term match is not relevance. A `.fastq.gz` from an
  unrelated assay that happens to share the word "development" is noise.
- **Describe at the right level.** Group by MOLNG request. A researcher wants
  "MOLNG-4089: 10x Multiome, APOE4 vs APOE3 organoids" — not 14 FASTQ filenames.
  Give representative paths and say how many files the request holds.
- **Never launder a guess into a fact.** State the tier. A `csv` file carries
  real request metadata; an `inferred` file is your reading of a folder name.
  Mark inferred entries plainly.
- **Never cite an `unknown`-tier file as relevant.** It is excluded from search
  by default for exactly this reason. Count them in the gaps instead.

Write to `output/<topic>_<YYYY-MM-DD>.md` using
`resources/report_template.md`. Bullets over paragraphs, per CLAUDE.md.

Then render the PDF companion — **every report ships as both `.md` and `.pdf`**:

```bash
./.venv/bin/python scripts/render_report.py output/<topic>_<YYYY-MM-DD>.md
```

The `.md` is the source of truth; the `.pdf` is derived and regenerated
whenever the `.md` changes. Re-run after any edit, or `--all` to sweep
`output/`. Never hand-edit a `.pdf`.

Two authoring conventions the renderer depends on:

- **Field lines** — `**Project:** ...`, `**Platform:** ...` — each stay on
  their own line in the PDF. Write them as consecutive lines; the renderer
  inserts the hard breaks.
- **A paragraph opening with ⚠️** renders as an amber caveat box. Use it for
  "this is inferred", "raw data only", and similar warnings a reader must not
  skim past.

## Step 7 — Gap analysis

This half is the point of the exercise, not an appendix. Read
`knowledge/coverage.json` and separate four distinct failure modes — they have
different remedies, so never merge them:

| Gap | Source | What it means |
| --- | --- | --- |
| Requested but never delivered | `requests_missing_no_path_in_csv` | The CSV has no path at all. Data may not exist. |
| Indexed but not in scope | `requests_missing_path_but_absent` | The CSV had a path, but no matching files in the scanned roots. Possibly untransferred, or outside your `--path`. |
| Present but undocumented | `files_by_tier.unknown` | Files on the endpoint no metadata explains. These are organization debt. |
| Unanswerable by any existing data | your judgment | No assay, tissue, timepoint, or contrast in the corpus addresses this aspect of the goal. |

That last row is the one researchers actually need. Say plainly what new
experiment or acquisition their question requires. Be specific: "no wild-type
VNO timepoint before P7 exists, so the critical-period onset comparison cannot
be made from these data."

Two standing caveats to carry into every report:

- **`Analysis Result Paths` is empty for all 70 requests.** No derived analysis
  output can be attributed by CSV join. Anything downstream of raw reads can
  only ever reach the `inferred` tier.
- **Every request is from the same lab.** The CSV cannot support any cross-lab claim.
- **The CSV indexes SEQUENCING ONLY.** Proteomics, EM, imaging, behavior and
  ephys have no MOLNG number and cannot appear in it. Never report "no data
  exists" on the strength of the CSV alone — search the association store,
  which covers everything scanned. The 2026-08-31 report made exactly this
  mistake and missed an entire APEX Aβ40/Aβ42 proteomics dataset.

## Step 8 — Log the run

```bash
./.venv/bin/python -c "
import sys; sys.path.insert(0,'scripts'); import kb
kb.append_query(run_id='<run-id>', goals='<goal>',
                filters={'types':'...','folders':['...']},
                results=[{'path':'...','score':0.0,'verdict':'included'}],
                gaps={'unanswerable':['...']},
                report_path='output/....md')"
```

Then regenerate the rollup: `./.venv/bin/python scripts/rollup.py`.

## Step 9 — Offer to record corrections

If the researcher says an inferred association is wrong, write it back as a
`human_correction`. These are gold labels — they outrank machine assertions
permanently and are what the future database-organization agent learns from.

```bash
./.venv/bin/python -c "
import sys; sys.path.insert(0,'scripts'); import kb
kb.append_association(collection_id='<uuid>', path='<path>',
    tier='csv', source='human_correction',
    metadata={'terms':['...'],'note':'confirmed by <who>'},
    confidence=1.0, evidence={'corrected_by':'<who>'}, run_id='manual')"
```

Also offer to add the missing term to `resources/vocab.json` so the same
mistake does not recur. Bump `version` when you do — associations record the
vocab version that produced them.
