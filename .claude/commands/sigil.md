---
description: Run sigil from the repo root - a digestible lab profile and interactive dashboard from forage's knowledge
argument-hint: "[anything to emphasize]"
---

Run the `sigil` agent in place, from the root.

**Read `.claude/lib/delegate.md` now and follow it with `<agent>` = `sigil`.**
That file is the single source of truth for delegation. Do not improvise the
steps.

## The request

$ARGUMENTS

Empty is fine: a profile needs no topic. Pass anything written here through
verbatim to `sigil/.claude/commands/sigil.md` as its `$ARGUMENTS`.

## Worth remembering here

- sigil needs no credentials. Step 3 of the protocol should report that it
  needs no environment.
- Its only input from outside `sigil/` is forage's exported snapshot. If that is
  missing or stale, sigil runs forage's exporter (local, read-only), never a
  forage scan, and never `/forage` itself.
- Outputs stay in `sigil/output/`. Nothing is published or uploaded; the
  internal edition carries site details.
