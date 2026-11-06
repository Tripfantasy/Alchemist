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

# Site notes

Facts about one specific collection (request-ID format, request counts, local
lessons) live in `CLAUDE.local.md` beside this file. It is gitignored. Claude
Code loads it automatically; a delegated run must read it explicitly, right
after this file. Where it exists it is binding, and where it is more specific
than this file it wins. Nothing site-specific belongs in this file.

# Invoking the discovery workflow

`/forage <goal>` runs it, or describe a research goal and the
`globus-discovery` skill triggers. Both route to workflows/data_discovery.md,
which is the single source of truth - read it, do not work from memory.

A site whose resources/site.json sets `"backend": "local"` (chosen in `/setup`)
also reads LOCAL.md, which adds local-path rules. It never applies to Globus.

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
- .zip archives are opaque to every scan: Globus lists a file, never what is
  inside it. After the first-pass search, ALWAYS run
  `scripts/zip_index.py --find <inventory> --folder <scope>`. It is local, with
  no network calls. If archives are in scope, ASK the researcher whether to look
  inside, with their size and date (workflow Step 3a). Never open one unasked,
  and never conclude data is absent while unopened archives remain in scope.
  Core facilities routinely archive finished pipeline output; an "absent"
  dataset is often inside one.
- Site resources follow one pattern: resources/<name> is the site's own copy
  (gitignored), resources/<name>.example (or _example) is the shipped default,
  and scripts prefer the site copy (kb.resource). This covers site.json
  (request-ID format), vocab.json, metadata.csv, project_codes.json and
  mouse_lines.json (built from the lab's colony list by
  `scripts/mouse_lines.py build`; the colony CSVs live in resources/colony/,
  also gitignored). Never read a colony column that names people.
- Mouse-line matches are path inferences: they can lift a file from `unknown`
  to `inferred`, never to `csv`. Run `mouse_lines.py probe` on an inventory
  after any registry change and look for false matches before re-indexing.
- resources/vocab.example.json is a STARTER vocabulary. Copy it to vocab.json
  and grow it from the site's own metadata and folder names. Refusals in
  `ambiguous` are collection-specific judgments: record the evidence for each in
  `_comment`, and re-derive them on a new collection rather than inheriting them.

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
- knowledge/snapshot.json - aggregated export for other agents
  (scripts/export_snapshot.py; schema 2 adds `mouse_lines`). forage's ONE public interface: sigil reads this
  and nothing else of forage's. Aggregates only, never per-file records. Bump
  `schema` on any shape change; consumers refuse an unknown one.

Three invariants the future organizing agent depends on:

1. Append only. A changed association is a new record with `supersedes`, never
   an edit. The history shows where metadata is unstable.
2. Path is not an identity. Paths change during transfer to Globus, so every
   record also stores request-ID/flowcell anchors.
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

scripts/zip_index.py also reads over HTTPS (a token for the collection's
`https` scope). Same binding layer: the `r` permission. Its in-process
backstops are a GET/HEAD-only session, a per-archive byte cap
(`--max-index-mb`, default 256), and a hard stop if the server ignores a Range
header. It reads an archive's index into memory and never writes fetched bytes
to disk. That is reading, not copying. Extracting a member is a download, and
is never this agent's job.

Never grant the client `rw` or an access-manager role, even temporarily. No
task in this project needs write access. Never verify read-only by attempting
a write - a test that creates a directory when it fails is worse than no test.
Run scripts/verify_readonly.py instead.

The client secret lives in the macOS Keychain (service
`globus_agent_client_secret`), never in the repo or in code.

# Data Notes

- resources/metadata.csv is the sequencing core's request export (gitignored;
  metadata_example.csv ships with synthetic rows).
- The request ID (format set in resources/site.json) is the primary join key;
  flowcell IDs are secondary.
- CSV result paths are usually PRE-TRANSFER and do not exist on the Globus
  collection. Join on tokens extracted from paths, never on paths themselves.
- If `Analysis Result Paths` is unpopulated, derived analysis output cannot be
  attributed by CSV join - flag this limitation in every report.
- THE CSV INDEXES SEQUENCING ONLY. Proteomics, EM, imaging, behavior and ephys
  have no request number and cannot appear in it. Never conclude "no data
  exists" from the CSV alone - search the association store, which covers
  everything scanned. A whole proteomics dataset in a directory the CSV never
  indexed is exactly what that mistake misses.
- Many catalogued requests may have only .html QC reports on the endpoint, not
  datasets. Check file types before claiming a request is "available".