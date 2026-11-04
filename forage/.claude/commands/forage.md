---
description: Find existing Globus data matching a research goal, and report what it cannot answer
argument-hint: "[research goal] [--quick for a judged file list, no report]"
---

Run the data discovery workflow.

**Read `workflows/data_discovery.md` now and follow it.** That file is the
single source of truth for this procedure — do not work from memory, and do not
paraphrase its steps. If anything here conflicts with it, that file wins.

## Research goal

$ARGUMENTS

If that is empty, ask for the goal before doing anything else.

## Which mode

`--quick` anywhere in those arguments selects quick-match; strip it before
passing the rest to `search.py` as the goal. Anything else is a full run. The
workflow's **Two modes** table is authoritative — read it rather than inferring
the difference.

Quick-match answers on screen: a judged, tier-labelled file list, a line on what
was cut, and a scope line. No `output/` file, no `.pdf`. Its two hard edges:

- **It never touches the network.** No survey, no scan, at any depth. If the
  association store does not cover the requested roots, it stops and hands back
  the full `/forage <goal>` rather than scanning.
- **It still judges.** `search.py` is a recall device that knows no biology, so
  its ranking is never the answer. Cut the false positives, group by
  request, and label every path `[csv]` or `[inferred]`. A terse format is where
  an unlabelled guess slips through, and quick answers get trusted fastest.

## Standing context for this collection

- Collection: `$GLOBUS_AGENT_COLLECTION_ID` — a guest collection, read-only.
  Both it and `GLOBUS_AGENT_CLIENT_ID` are set by `.claude/settings.json`,
  which is gitignored. Never hardcode either UUID, and never write one into a
  report. The secret is in the macOS Keychain under `globus_agent_client_secret`
- **Always use `./.venv/bin/python`**, never bare `python3` — `globus-sdk` and
  `markdown` are installed only in the venv

## Non-negotiable

READ-ONLY on Globus. Never transfer, rename, delete, or create anything on the
collection, and never suggest granting the client `rw` "temporarily". The
binding protection is the collection permission, not the in-process guard.

## Before scanning, check what already exists

`knowledge/inventory.jsonl` and the association store may already cover the
question. A full re-scan takes hours. Reuse unless the roots differ or the tree
has changed; re-index only if `resources/vocab.json` changed since the last build.

## The CSV is not the collection

`resources/metadata.csv` indexes **sequencing requests only**. Proteomics,
EM, imaging, behavior and ephys have no request number and are invisible to it.

A report that concludes "no such data exists" on the strength of that CSV can
miss a whole dataset sitting in a directory the CSV never indexed.
**Never treat absence from the CSV as absence from the collection.** Search the
association store, which covers everything scanned, before declaring any gap.

## Deliverable

On a full run, both `.md` and `.pdf` in `output/`, per
`resources/report_template.md`:

```bash
./.venv/bin/python scripts/render_report.py output/<name>.md
```

On a `--quick` run, the screen — no file, and no `render_report.py`.

Either way, log the run to `knowledge/query_log.jsonl` (workflow Step 8). Quick
runs log with `report_path=''`; skipping them would leave the store describing
only the rarer half of what researchers ask.
