---
description: Run distill from the repo root - research a topic end-to-end and produce a structured, cited report
argument-hint: "<topic>"
---

Run the `distill` agent in place, from the root.

**Read `.claude/lib/delegate.md` now and follow it with `<agent>` = `distill`.**
That file is the single source of truth for delegation. Do not improvise the
steps.

## The topic

$ARGUMENTS

If that is empty, ask for a topic before doing anything else.

## Worth remembering here

`distill/.claude/commands/distill.md` declares an `allowed-tools` list. Running
from the root does not apply it, so the usual restriction to
Read/Write/Glob/Grep/WebSearch/WebFetch/AskUserQuestion/Bash is not enforced for
you. Stay inside it anyway — treat the list as the rule it is meant to be.

Provenance tiering is the deliverable's backbone. A claim's tier travels with
it, and running from the root changes nothing about that.
