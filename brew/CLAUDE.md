# Project Context

For this project, I want to design an agent that takes the user's prompt, as well as either the link to a research paper, or a .pdf of the paper itself. The goals are as follows:

1. Provide summarised, digestable workflows of either the wet-lab experiments or computational analysis, or both. This would be delivered in a step by step protocol-esque report. It should always be transparent about the limits of documentation, and mention what details are missing from the paper. 

2. For queries regarding computational analysis, the output is similar, but should also include environment details (packages, software, recommended resources) And should check if the paper has supplemental code repositories (GitHub) with analysis code. If the code exists, create a summarised workflow (either .rmd or jupyter notebook) with well documented steps so that users can reproduce the analysis. 

3. Any public data (GEO accessions) that are available through the paper should be taken advantage of and encorpoorated into the analysis reproduction. This it the ETL step. Prepare workflow to handle a variety of sequencing data, but should prefer .h5 or matrix equivalents to raw fastQ data. Ask users clarifying questions to gauge which aspect of the analysis they are wanting to work on / explore. 

# About Me

I am a bioinformatician working in a neuroscience department. I am responsible for guiding researchers to data that best fits their research goals, and I have a vested interest in making publicly available data and research interpretable, transferrable, and reproducible. 

# Rules

- Always ask clarifying questions before starting a complex task.
- Show your plan and steps before executing.
- Keep reports and summaries concise. Bullet points over paragraphs.
- Save all output files to the output folder.
- Every report ships as BOTH .md and .pdf. Write the .md, then run
  `./.venv/bin/python scripts/render_report.py output/<name>.md`. The .md is the source of
  truth; the .pdf is derived - never hand-edit it, regenerate it.
- Only read the files in the globus directories, NEVER edit, move, or copy files under any circumstances. 
- Never launder an inference into a fact. Every protocol step is tiered `stated`
  (in the paper), `repo` (in the authors' code), **[inferred]** (supplied by the
  agent), or `missing` (unrecoverable). A plausible parameter the paper never
  gave is [inferred], with the assumption spelled out - writing it bare is
  fabrication. Never cite a repo file or accession you have not fetched.
- NO DATA DOWNLOADS. Probe accession metadata, then write ETL code for the user
  to run. Notebooks ship unrun, with empty outputs - never paste fabricated
  results into a cell.

# Invoking the reproduction workflow

`/brew <paper URL, DOI, or PDF path>` runs it, or describe a paper you want
reproduced and the `paper-reproduction` skill triggers. Both route to
workflows/paper_reproduction.md, which is the single source of truth - read it,
do not work from memory. Its data half is workflows/etl_geo.md.

# Environment

- ALWAYS use ./.venv/bin/python, never bare python3. `markdown` (for the PDF
  renderer) is installed only in the venv.
- The venv is the AGENT's tooling, not an analysis environment. Generated
  notebooks mirror the paper's own stack and declare their own dependencies;
  this project installs no scanpy/Seurat and runs no analysis.
- Reading papers: local PDFs with the `Read` tool (`pages` is required above 10
  pages, 20 pages max per call). For URLs and DOIs, prefer the literature
  connectors below over the open web; `WebFetch`/`WebSearch` are the fallback
  (load them with `ToolSearch` -> `select:WebSearch,WebFetch`).
- The PubMed / bioRxiv / Scite connectors ARE authorized and working (verified
  2026-09-08). Their schemas are deferred, so load them first with `ToolSearch`,
  e.g. `select:mcp__claude_ai_PubMed__search_articles,mcp__claude_ai_Scite__search_literature`.
  Source preference for method extraction, best first:
  1. **Local PDF + supplements** - still the richest source when the user has one.
  2. **Scite `search_literature`** with `dois` + a `term` - returns full-text
     excerpts for the passage you asked about, so query it once per method
     section ("library prep", "clustering resolution"). Also carries
     `editorialNotices` - check every paper for retractions/corrections BEFORE
     building a protocol from it - and an `access` link when the text is paywalled.
  3. **PubMed** - `search_articles` to resolve a citation, `convert_article_ids`
     for PMID -> PMCID, then `get_full_text_article` for the PMC full text.
     Requires citing PubMed and the article DOI wherever its content is used.
  4. **bioRxiv `get_preprint`** by DOI for preprints. Note `search_preprints`
     has NO keyword search - date range and category only - so it cannot find a
     named preprint; go by DOI.
  Connector text is a source like any other: it feeds the `stated` tier only for
  what it actually says, and never substitutes for fetching a repo file.

# Project Structure

- workflows/ - Workflow instruction files (plain English recipes the agent follows)
- output/ - Finished deliverables (reports, drafts, notebooks)
- resources/ - Reference docs and templates
- scripts/ - Utility scripts when calling specific tools and functions.
- data/ - Landing zone for public data, one directory per accession, gitignored.
  Written by the USER running the generated ETL, not by the agent. Only
  probe.json and samples.csv are kept in git.

