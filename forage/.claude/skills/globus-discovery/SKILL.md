---
name: globus-discovery
description: Find existing data on the configured Globus collection that matches a researcher's project or goals, and report which aspects the available data cannot address. Use whenever someone asks what data already exists for a research question, wants a manifest of relevant files or datasets, asks whether the lab already has data on a topic/assay/tissue/genotype, or needs to know what is missing before designing an experiment. Also use for questions about the knowledge store, undocumented files, or organization debt on the collection.
---

# Globus Data Discovery

Read `workflows/data_discovery.md` and follow it. That file is the single source
of truth — do not work from memory or paraphrase its steps.

Then read `.claude/commands/forage.md` for the standing collection context
(collection UUID, credentials, venv, and the CSV-coverage lesson).

## The three things that matter most

1. **Read-only on Globus, always.** Never transfer, rename, delete, or create.
   Never propose granting the client `rw`, even temporarily.
2. **`resources/metadata.csv` covers sequencing requests only.**
   Proteomics, EM, imaging, behavior and ephys are invisible to it. Absence from
   the CSV is not absence from the collection — check the association store in
   `knowledge/` before declaring any gap. A previous report got this wrong and
   missed an entire APEX Aβ40/Aβ42 proteomics dataset.
3. **Never launder a guess into a fact.** Every claim carries a tier: `csv`
   (matched a request record), `inferred` (read off a path), or `unknown` (too
   vague — recorded, never reported as understood). Mark inferred entries plainly.

## Deliverable

Both `.md` and `.pdf` in `output/`, then log the run to
`knowledge/query_log.jsonl`. Use `./.venv/bin/python`, never bare `python3`.
