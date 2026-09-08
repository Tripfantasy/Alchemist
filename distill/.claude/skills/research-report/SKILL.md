---
name: research-report
description: Research a topic end-to-end and produce a structured, cited report ending in actionable recommendations. Use whenever someone asks for research on a topic, a literature review or state-of-the-field summary, a comparison of methods/tools/approaches to decide between them, background for a grant or proposal, or an evidence-backed answer to "what do we know about X". Also use when someone wants sources gathered and assessed on a question, or asks whether a claim is supported by the literature.
---

# Research Report

Read `workflows/research-report.md` and follow it. That file is the single
source of truth — do not work from memory or paraphrase its phases.

## The three things that matter most

**1. Intake is not optional.** Phase 0 runs even when the topic looks
self-explanatory. One batched round of 3–4 questions via `AskUserQuestion`,
then work — no second round, no follow-up trickle. The whole value of the
workflow is that research targets the right thing on the first pass.

**2. Options must come from the topic.** "Broad vs. narrow" tells you nothing,
because the user has to translate it into their real situation anyway. Spend
30 seconds identifying the topic's actual dividing lines — competing
approaches, sub-fields, scope boundaries — and offer those instead.

**3. The report ends in a decision.** Question 3 of intake asks what decision
the research informs. The Recommendations section answers that question
specifically; a report that merely informs has missed the point.

## Sources

Prefer the PubMed / bioRxiv / Scite connectors over the open web for scientific
literature when they're authorized; their schemas are deferred, so load them
with `ToolSearch` first. `WebSearch` / `WebFetch` are the general fallback —
load them the same way if they aren't present.

`resources/source-quality.md` is the standard for what counts as usable, and
depth tiers (Brief / Standard / Deep) set how many sources the report needs.
Never cite a source you have not actually retrieved.

## Deliverable

Both `.md` and `.pdf` in `output/`, named `YYYY-MM-DD_<topic-slug>`, following
`resources/report-template.md`:

```bash
./.venv/bin/python resources/md-to-pdf.py output/<name>.md
```
