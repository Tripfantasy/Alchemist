---
description: Find existing Globus data matching a research goal, and report what it cannot answer
argument-hint: "[research goal, in your own words]"
---

Run the data discovery workflow.

**Read `workflows/data_discovery.md` now and follow it.** That file is the
single source of truth for this procedure — do not work from memory, and do not
paraphrase its steps. If anything here conflicts with it, that file wins.

## Research goal

$ARGUMENTS

If that is empty, ask for the goal before doing anything else.

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

## The lesson from the first run

`resources/metadata.csv` indexes **sequencing requests only**. Proteomics,
EM, imaging, behavior and ephys have no MOLNG number and are invisible to it.

A previous report concluded "no mouse OE/OB Alzheimer's data exists" on the
strength of that CSV. It was wrong — a large APEX Aβ40/Aβ42 proteomics dataset
was sitting in a top-level proteomics directory the CSV never indexed.
**Never treat absence from the CSV as absence from the collection.** Search the
association store, which covers everything scanned, before declaring any gap.

## Deliverable

Both `.md` and `.pdf` in `output/`, per `resources/report_template.md`:

```bash
./.venv/bin/python scripts/render_report.py output/<name>.md
```

Then log the run to `knowledge/query_log.jsonl` (workflow Step 8).
