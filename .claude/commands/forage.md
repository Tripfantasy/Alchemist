---
description: Run forage from the repo root - find existing Globus data matching a research goal
argument-hint: "[research goal, in your own words]"
---

Run the `forage` agent in place, from the root.

**Read `.claude/lib/delegate.md` now and follow it with `<agent>` = `forage`.**
That file is the single source of truth for delegation. Do not improvise the
steps, and do not skip the environment check — forage is the one agent that
will not run without it.

## Research goal

$ARGUMENTS

If that is empty, ask for the goal before doing anything else — but ask it as
part of the intake round, not instead of it.

## The two things most likely to go wrong here

**Credentials.** `GLOBUS_AGENT_CLIENT_ID` and `GLOBUS_AGENT_COLLECTION_ID` come
from `forage/.claude/settings.json`, which a root session does not read. Step 3
of the protocol catches this. Run `sync`, re-run `check`, and if it still fails
say plainly that the session needs restarting rather than trying to route
around it with inline exports.

**Scope.** Never launch a scan without scoping it first. Survey at `--depth 2`,
show the real top-level directories with their actual cost, and scan only what
the researcher picks. A full scan is ~3 hours; `--path` is repeatable. Reuse
`knowledge/inventory.jsonl` if its `scan_meta` header already covers the roots.

## Non-negotiable

READ-ONLY on Globus. Never transfer, rename, delete, or create anything on the
collection, and never suggest granting the client `rw` "temporarily". Running
from the root does not relax this by one inch — `forage/CLAUDE.md`, which you
load in Step 2, is binding for this run.

Never write a collection or client UUID into a report, a doc, or the transcript.
