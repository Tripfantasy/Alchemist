---
description: Run brew from the repo root - turn a paper into a runnable protocol plus an audit of what it omits
argument-hint: "[paper URL, DOI, PMID, or path to a PDF] [what you want from it]"
---

Run the `brew` agent in place, from the root.

**Read `.claude/lib/delegate.md` now and follow it with `<agent>` = `brew`.**
That file is the single source of truth for delegation. Do not improvise the
steps.

## The paper

$ARGUMENTS

If that is empty, ask for a paper before doing anything else. A DOI, PMID, URL,
or local `.pdf` path all work.

## Worth remembering here

Downloads land in `brew/data/`, never in the root — and they can be tens of GB
per series, so confirm before pulling one.

`[inferred]` steps are the whole point of the output: a step the paper does not
actually document must never read as one it does. Delegation does not soften
that labelling.
