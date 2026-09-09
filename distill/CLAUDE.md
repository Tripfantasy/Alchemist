# Project Context

# About Me

I am a bioinformatician working in a neuroscience department. I have a vested interest in database organization, and improving complex computational biological methods. My analyses and developed tools are for the benefit of lab members, and the neuroscience department. They must be credible, well-researched, and interpretable. 

# Rules

- Always ask clarifying questions before starting a complex task.
- Show your plan and steps before executing.
- Keep reports and summaries concise. Bullet points over paragraphs.
- Save all output files to the output folder.
- Cite sources when doing research. Never cite a source you have not retrieved.
- NO UNPROMPTED LOCAL PRIORS. A run reads nothing outside this project's
  `resources/` unless the user names a path in the Phase 0 intake round. That
  means no filesystem `Glob`/`Grep` for context, no reading past reports in
  `output/`, and no treating the "About Me" above as an answer to a question
  intake should ask. The profile says who is asking, not what was asked.
  Whatever a run did read is disclosed in the report's Scope section.
- Every report ships as BOTH .md and .pdf. Write the .md, then run
  `./.venv/bin/python resources/md-to-pdf.py output/<name>.md`. The .md is the
  source of truth; the .pdf is derived - never hand-edit it, regenerate it.

# Invoking the research workflow

`/distill <topic>` runs it, or describe a topic you want researched and the
`research-report` skill triggers. Both route to workflows/research-report.md,
which is the single source of truth - read it, do not work from memory.

# Environment

- ALWAYS use ./.venv/bin/python, never bare python3. `markdown` (for the PDF
  renderer) is installed only in the venv.
  Setup: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt`
- PDF rendering needs a Chrome-family browser (Chrome, Chromium, Edge, Brave),
  found by path or on PATH.
- This workflow needs `WebSearch` and `WebFetch`; their schemas are deferred, so
  load them with `ToolSearch` -> `select:WebSearch,WebFetch`. For scientific
  literature the PubMed / bioRxiv / Scite connectors are usually better sources
  than the open web - load them the same way, and fall back to the open web
  (saying so) if they are not authorized.

# Project Structure

- workflows/ - Workflow instruction files (plain English recipes the agent follows)
- output/ - Finished deliverables (reports, drafts, analysis)
- resources/ - Reference docs and templates