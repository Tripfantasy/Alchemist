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

## Step 0 — The bias-reporting question (separate, and additional)

Asked once per session, before intake.

**It does not use an intake slot.** Separate `AskUserQuestion` call, one
question; Step 1 still gets its full 3–4. Never drop or merge an intake question
to make room — those determine which files come back, and a session preference
must not be paid for out of that budget.

```bash
python3 ../bias/report.py status --session <session-id>
```

- **`asked already : yes`** — don't ask again; use the reported state.
- **`asked already : NO`** — ask:

> Enable bias reporting for this session?
> - **No** — the default. Reports carry no influence section
> - **Yes** — each report gains a *Context & Influence* section listing what shaped it besides your request, and runs accumulate in `bias/log.jsonl` for a cross-run view

Record the answer yourself — **never ask the user to run a command**:

```bash
python3 ../bias/report.py set --enabled true|false --session <session-id>
```

No session id available? Use "have I already asked in this conversation?" as the
test. An answer the user already gave in conversation stands — record it and
skip the question.

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
   **Do not ask this one blind.** A researcher cannot name path prefixes on a
   collection they have not seen, and "the whole collection" is what they will
   pick by default — which is the three-hour answer. Run the survey in Step 2a
   first and ask with the actual top-level directories as options.

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

## Step 2 — Check what you already have, before proposing any scan

**A scan is the most expensive thing this workflow can do — three hours at the
full depth. Never launch one before establishing that the existing inventory
cannot answer the question.** Two failure modes, and the second is the common
one: re-scanning a tree already covered, and scanning the whole collection when
the researcher only ever cared about one directory.

Every inventory's first line is a `scan_meta` header recording exactly what it
covers — roots, depth, types, exclusions, timestamp. Read it rather than
guessing:

```bash
./.venv/bin/python -c "
import json, pathlib
p = pathlib.Path('knowledge/inventory.jsonl')
if not p.exists():
    print('no inventory -- a scan is genuinely needed'); raise SystemExit
with p.open() as fh:
    m = json.loads(fh.readline())
print('scanned  :', m['ts'])
print('roots    :', m['roots'])
print('depth    :', m['depth'])
print('types    :', m['types'] or 'all')
print('excluded :', m['exclude'] or 'nothing')"
```

Then decide, in this order:

| Existing inventory | Do this |
| --- | --- |
| Covers the requested roots at sufficient depth | **Reuse it.** Skip to Step 4. Say in the report when it was scanned |
| Covers a superset, but is months old | Reuse, and flag the date in the report. Offer a re-scan; do not launch one unasked |
| Covers a *sibling* tree, not the requested one | Scan **only the missing roots** and merge — not the whole collection again |
| Was scanned with `--types` narrowing the walk | Treat as incomplete for any other type. This is why Step 3 scans without `--types` |
| Missing, or the requested root was never walked | Go to Step 2a |

## Step 2a — Survey before you scan

A researcher cannot choose path prefixes on a collection they have never seen,
and asking them to will reliably produce "scan everything". So map the top of
the tree first — this costs seconds, not hours:

```bash
./.venv/bin/python scripts/scan_endpoint.py <COLLECTION_UUID> \
    --path / --depth 2 \
    --out knowledge/survey.jsonl
```

Depth 2 is the useful setting: depth 1 gives bare directory names that mean
nothing to a researcher, while depth 2 shows what is one level inside each and
usually reveals whether a directory holds data, archives, or someone's scratch.

Summarize what came back — directory, what appears to be in it, rough file
count — and **then** ask the folder-scope question from Step 1 with those
directories as real options:

> The collection has these top-level directories. Which should the scan cover?
> - **`/projects/` only** — ~40k files. Where the MOLNG sequencing requests live
> - **`/projects/` + `/proteomics/`** — adds the APEX mass-spec data the CSV never indexes
> - **`/imaging/`** — ~1.7M files, mostly per-trial microscopy. Hours to walk
> - **Everything** — the full ~3-hour scan
>
> *(Answer "Other" with specific paths if you already know where to look.)*

Rules for this round:

- **Put the real cost in the option text.** "Everything — ~3 hours" lets someone
  choose it deliberately. "Everything" alone gets chosen by default, and the
  cost only surfaces once the scan is already running.
- **Offer a narrow default first.** Most goals are answered by one or two
  directories. A researcher asking about stroke imaging does not need the
  sequencing tree walked.
- **Ask about depth only when the survey shows it matters** — a tree of
  instrument session folders needs depth 5; a flat directory of `.h5ad` files
  does not. Otherwise use the established default and say so.
- **Offer exclusions when the survey reveals an obvious sink** — `--exclude`
  takes substrings, and skipping a backup or EndNote tree can halve a walk.
- The survey inventory is throwaway. Do not index it, and do not report from it.

## Step 3 — Scan the agreed scope

```bash
./.venv/bin/python scripts/scan_endpoint.py <COLLECTION_UUID> \
    --path /projects/ --path /proteomics/ \
    --depth 5 \
    --exclude /backup/ \
    --out knowledge/inventory.jsonl
```

`--path` is repeatable — pass the directories the researcher chose in Step 2a
rather than defaulting to `/`. **A full scan of this collection takes ~3 hours**;
a two-directory scan is minutes. That difference is the entire point of Steps 2
and 2a.

`--depth 5` is the established setting: it reaches inside instrument session
folders without descending into per-trial subdirectories. Depth 8 was tried and
abandoned as impractical.

Scan WITHOUT `--types` so one inventory serves every future query; filter per
question in `search.py` instead. `--types` here narrows the *walk*, which
permanently limits what that inventory can answer — the type filter belongs in
`search.py`, where it is free and reversible.

**Scanning additional roots later:** write to a separate file
(`--out knowledge/inventory_proteomics.jsonl`) rather than overwriting an
inventory that took hours to build. Then run Step 4 once per inventory —
`--inventory` takes a single path, and the association store is append-only, so
two runs accumulate correctly.

⚠️ `coverage.json` does **not** accumulate: it is rebuilt from whichever
inventory was indexed last. After indexing several, the gap analysis in Step 7
describes only the last one. Index the inventory the goal actually depends on
last, and say in the report which roots the coverage numbers cover.

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

### Bias reporting (if it was enabled in Step 0)

Only when the Step 0 question turned it on. Append a **Context & Influence**
section to the report and log the run with
`python3 ../bias/report.py append --file <scratchpad>/bias_run.json`. Format and
record shape are in `../bias/README.md`.

forage has the most standing priors of the three agents, and they are the point
of it — a knowledge store that did not accumulate would be useless. Record where
they actually steered *this* run:

- **`knowledge_store`** — prior queries in `query_log.jsonl` that shaped these
  search terms or rankings
- **`vocab`** — terms this collection's v6 vocabulary refused or matched, which
  another collection would treat differently. The `pt` refusal excluding
  stroke-labelled paths is the worked example
- **`claude_md_profile`** — anything the About Me block supplied that the intake
  round did not ask

The distinction that matters: a vocabulary *matching* a term is the system
working. A vocabulary *narrowing the answer* to what previous runs asked about
is drift. Log the second.

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

### The vocabulary ships populated, and it is site-specific

`resources/vocab.json` is **not** empty on a fresh clone. It ships at v6 with
roughly 250 terms across `tissue`, `assay`, `gene`, `species`, `condition` and
`stage`, plus a `ambiguous` refusal list. First runs do not start from nothing.

But it was **seeded from one lab's `metadata.csv`**, and it carries that
collection's idiosyncrasies as deliberate decisions:

- `oe`, `vno`, `aob` and the rest of the olfactory vocabulary, because that is
  what this lab studies
- `pt` **refused** in `ambiguous`, because on this collection it means
  photothrombotic, PT_Rabies, EndNote page ranges and model checkpoints all at
  once — measured at only ~40% correct
- `peri`, `nc` and `7d` refused for the same reason, each on evidence recorded
  in the file's `_comment`

**On a different collection those refusals are wrong.** `pt` may be unambiguous
elsewhere; the olfactory terms may be dead weight. So on a new collection:

- Read the `_comment` block first. Every refusal records the evidence that
  produced it, which is what makes it safe to reverse.
- Treat the domain sections as a starting point to prune, not a fixed schema.
- Re-derive `ambiguous` against the new tree. A term refused on 40% precision
  here may be perfectly clean there, and refusing it silently costs recall.
- Bump `version` and describe the change in `_comment` — associations stamp
  `vocab_version`, so the store stays interpretable across the edit.

The `_comment` block is the vocabulary's changelog and its evidence. Never edit
a term without adding to it; a refusal with no stated reason cannot be safely
reversed later.
