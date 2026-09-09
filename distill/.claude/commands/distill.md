---
description: Research any topic end-to-end and produce a structured, cited report
argument-hint: "<topic>"
allowed-tools: Read, Write, Glob, Grep, WebSearch, WebFetch, AskUserQuestion, Bash
---

Run the research report workflow.

**Read `workflows/research-report.md` now and follow it, start to finish.** That
file is the single source of truth for this procedure — do not work from memory,
and do not paraphrase its phases. If anything here conflicts with it, that file
wins.

## The topic

$ARGUMENTS

If that is empty, ask for a topic before doing anything else.

## Order of operations

1. **Never skip Phase 0 (intake)** — it runs even when the topic looks
   self-explanatory, and even when the request already contains detail.
2. Ask **one** batched round of 3–4 questions in a single `AskUserQuestion`
   call, then start working. No second round.
3. Every option must name a real dividing line in *this* topic. Generic
   "broad vs. narrow" options waste the round.
4. **Slot P is mandatory**: ask whether the search may reference a local file
   or directory, or literature only. Default is literature only — read nothing
   outside `resources/` unless the user names a path in this round.
5. **Slot S fires when the topic references the user's own analysis output**
   (marker lists, DE genes, "annotate these clusters"). Ask for organism,
   tissue, genotype and stage *now*. Reporting the annotation as "ambiguous
   without knowing the tissue" after the search is the failure this prevents.

## Standing context

- If `WebSearch` or `WebFetch` aren't loaded, fetch them first with `ToolSearch`
  using the query `select:WebSearch,WebFetch`.
- For scientific literature, the PubMed / bioRxiv / Scite connectors are
  usually a better source than the open web when authorized. Their schemas are
  deferred — load them with `ToolSearch` first. Fall back to the open web and
  say so if they aren't available.
- Cite every claim that isn't common knowledge. `resources/source-quality.md`
  is the standard for what counts as a usable source.

## Deliverable

Both `.md` and `.pdf` in `output/`, named `YYYY-MM-DD_<topic-slug>`, following
`resources/report-template.md`. The Markdown is the source of truth.

```bash
./.venv/bin/python resources/md-to-pdf.py output/<name>.md
```

Hand back the file paths and the report's headline recommendation.
