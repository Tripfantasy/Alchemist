# Project Context

For this project, I want to design an agentic companion which interfaces with globus API, that can take a user input which describes their project, goals, and desired data formats, and return a manifest of files which may best help them accomplish their goals. 

The deliverable for this is a concise report which lists the related file paths, as well as their descriptions based on metadata. The report should also address the aspects of their project which the currently available data cannot address sufficiently. 

# About Me

I am a bioinformatician working in a neuroscience department. I have a vested interest in database organization, while being responsible for guiding researchers to previously generated data that best fits their research goals. 

# Rules

- Always ask clarifying questions before starting a complex task.
- Show your plan and steps before executing.
- Keep reports and summaries concise. Bullet points over paragraphs.
- Save all output files to the output folder.
- Every report ships as BOTH .md and .pdf. Write the .md, then run
  `./.venv/bin/python scripts/render_report.py output/<name>.md`. The .md is the source of
  truth; the .pdf is derived - never hand-edit it, regenerate it.
- Only read the files in the globus directories, NEVER edit, move, or copy files under any circumstances. 

# Invoking the discovery workflow

`/forage <goal>` runs it, or describe a research goal and the
`globus-discovery` skill triggers. Both route to workflows/data_discovery.md,
which is the single source of truth - read it, do not work from memory.

# Environment

- ALWAYS use ./.venv/bin/python, never bare python3. globus-sdk and markdown
  are installed only in the venv.
- GLOBUS_AGENT_CLIENT_ID and GLOBUS_AGENT_COLLECTION_ID come from
  .claude/settings.json, which is GITIGNORED - it holds private infrastructure
  UUIDs. Read the collection from $GLOBUS_AGENT_COLLECTION_ID; never hardcode a
  UUID into a doc, script, workflow or report, and never echo one into output/.
  The client secret is in the macOS Keychain under globus_agent_client_secret.
- A full scan takes ~3 hours at --depth 5. Reuse knowledge/inventory.jsonl
  unless the roots changed - its first line is a scan_meta header recording
  which roots, depth and types it covers, so check that instead of guessing.
- NEVER launch a scan without scoping it first. Survey the tree at --depth 2,
  show the researcher the actual top-level directories with their real cost,
  and scan only what they pick. --path is repeatable. "Scan everything" is a
  three-hour answer to a question that usually needs two directories.
- resources/vocab.json SHIPS POPULATED (v6, ~250 terms) - first runs do not
  build it from scratch. It is seeded from THIS lab's metadata.csv though, so
  its refusals in `ambiguous` (pt, peri, nc, 7d) are collection-specific
  judgments with their evidence recorded in `_comment`. On a new collection,
  re-derive them rather than inheriting them.

# Project Structure

- workflows/ - Workflow instruction files (plain English recipes the agent follows)
- output/ - Finished deliverables (reports, drafts, analysis)
- resources/ - Reference docs and templates
- scripts/ - Utility scripts when calling specific tools and functions.
- knowledge/ - Accumulating agent-written state, NOT deliverables. Append-only
  JSONL stores of file->metadata associations, plus the derived ASSOCIATIONS.md
  rollup. A planned database-organization agent will consume these.

# Knowledge Store

Persistent memory across runs. Owned exclusively by scripts/kb.py - never
hand-edit the JSONL files, and never write them from anywhere else.

- knowledge/file_associations.jsonl - every assertion ever made about a file
- knowledge/corrections.jsonl - human overrides; these are gold labels
- knowledge/query_log.jsonl - one record per discovery run
- knowledge/ASSOCIATIONS.md - regenerated human view; derived, never authored
- knowledge/inventory.jsonl - raw endpoint scan cache
- knowledge/coverage.json - gap-analysis inputs from the last index build

Three invariants the future organizing agent depends on:

1. Append only. A changed association is a new record with `supersedes`, never
   an edit. The history shows where metadata is unstable.
2. Path is not an identity. Paths already changed once during transfer to
   Globus, so every record also stores MOLNG/flowcell anchors.
3. Every assertion names its source (`csv_join`, `vocab_inference`,
   `model_judgment`, `human_correction`) and its confidence. A hard ID match
   and a guess off a folder name must never be indistinguishable downstream.

# Globus Access

Read-only, enforced in three layers. The binding one is the collection
permission, NOT the code.

1. The confidential client authenticates as <CLIENT_UUID>@clients.auth.globus.org
   and holds `r` (never `rw`) on the guest collection. Globus rejects writes
   server-side. This is the guarantee.
2. Globus Transfer has NO read-only scope - it is transfer.api.globus.org:all
   or nothing. Never suggest narrowing the scope; it is not possible.
3. ReadOnlyTransferClient in scan_endpoint.py blocks 12 mutating methods. A
   backstop only.

Never grant the client `rw` or an access-manager role, even temporarily. No
task in this project needs write access. Never verify read-only by attempting
a write - a test that creates a directory when it fails is worse than no test.
Run scripts/verify_readonly.py instead.

The client secret lives in the macOS Keychain (service
`globus_agent_client_secret`), never in the repo or in code.

# Data Notes

- resources/metadata.csv holds 70 sequencing requests, all from a single lab.
- `Request #` (MOLNG-####) is the primary join key; flowcell IDs are secondary.
- CSV paths (/n/analysis/...) are PRE-TRANSFER and do not exist on the Globus
  collection. Join on tokens extracted from paths, never on paths themselves.
- `Analysis Result Paths` is empty for all 70 rows. Derived analysis output
  cannot be attributed by CSV join - flag this limitation in every report.
- THE CSV INDEXES SEQUENCING ONLY. Proteomics, EM, imaging, behavior and ephys
  have no MOLNG number and cannot appear in it. Never conclude "no data exists"
  from the CSV alone - search the association store, which covers everything
  scanned. The 2026-08-31 report made this mistake and missed an entire APEX
  Ab40/Ab42 proteomics dataset in a top-level proteomics directory the CSV never indexed.
- Only ~21% of catalogued requests have real data on the endpoint; many MOLNG
  entries are .html QC reports, not datasets. Check file types before claiming
  a request is "available".