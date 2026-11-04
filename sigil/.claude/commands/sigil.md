---
description: Build a digestible lab profile and interactive dashboard from forage's knowledge of the collection
argument-hint: "[anything to emphasize]"
---

Run the lab-profile workflow.

**Read `workflows/lab_profile.md` now and follow it, start to finish.** That
file is the single source of truth for this procedure. Do not work from memory
or paraphrase its steps. If anything here conflicts with it, that file wins.

## The request

$ARGUMENTS

Empty is fine: a profile needs no topic. Anything written here is a preference
for emphasis, and it does not replace the intake round.

## Order of operations

1. Step 0: the bias question, asked separately.
2. Step 1: check forage's snapshot BEFORE intake; the intake options come from it.
3. Step 2: on the first run, ask for the lab's description, name, and the PI's
   name, institutions and ORCID, in the researcher's own words.
4. Step 3: fetch the five most recent lab papers from PubMed; confirm them
   with the researcher on the first run.
5. Step 4: the intake round, with theme names drawn from the snapshot.
6. Steps 5–7: build, write both editions, look at the dashboards.
7. Step 8: hand back with the collaborator review. Never imply the
   collaborator edition is cleared to share until the researcher says so.

## Non-negotiable

- Read-only outside `sigil/`. The only foreign file read is
  `../forage/knowledge/snapshot.json`.
- Nothing is published or uploaded. Outputs stay in `output/`. The only
  outbound request is the PubMed search, with the PI's public identifiers.
