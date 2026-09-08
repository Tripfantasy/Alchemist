# Alchemist

An agentic framework for expediting research lab tasks.

| Agent | Command | Input | Output |
| --- | --- | --- | --- |
| [distill/](distill/) | `/distill <topic>` | A topic | Cited research report with recommendations |
| [brew/](brew/) | `/brew <paper>` | A paper (URL, DOI, or PDF) | Reproduction protocol, an analysis notebook, and a list of what the paper fails to document |
| [forage/](forage/) | `/forage <goal>` | A research goal | List of matching files on a Globus collection, read-only |

Each agent's command is named after the agent. You can also just describe what
you want in plain language — each agent has a skill that triggers on the kind of
request it handles.

The agents are independent — use any one on its own. Only `brew` is tied to a
field: its data half targets GEO accessions, so it works best on papers with
public sequencing data. Its protocol and gap audit work for any paper. Examples
throughout use biology.

Start Claude Code **inside an agent's directory**. That is what loads its
`CLAUDE.md`, workflows, and slash command; running from the repo root will not.

---

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3.9+
- Chrome, Chromium, Edge, or Brave — run headless to make PDFs. No LaTeX needed.
- macOS. See [Limitations](#limitations) for what is and isn't portable.

Each agent has its own venv:

```bash
cd <agent>
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

`forage` needs Globus credentials as well, but only for real collection access.
Its demo runs without them.

---

## distill — research reports

```bash
cd distill && claude
```

```
/distill <your topic>
```

Or describe a topic and the `research-report` skill triggers.

The agent asks 3–4 intake questions in one round — scope, audience,
sub-questions, emphasis — then researches and writes. The answers determine what
the report covers. Depth ranges from Brief (~1 page, 5–8 sources) to Deep
(8–12 pages, 40+ sources).

Render the PDF:

```bash
./.venv/bin/python resources/md-to-pdf.py output/2026-09-08_your-topic.md
```

Example: [`EXAMPLE_research_report.md`](distill/output/EXAMPLE_research_report.md)

---

## brew — paper reproduction

```bash
cd brew && claude
```

```
/brew https://doi.org/<your-doi>   what does Fig. 2 take to redo?
/brew ~/Downloads/paper.pdf
```

The agent reads the paper, asks 3–4 questions naming that paper's figures, then
writes a protocol and a notebook (`.ipynb` or `.Rmd`, matching the stack the
paper's authors used).

Every protocol step is labelled with where it came from:

| Tier | Meaning |
| --- | --- |
| `stated` | In the paper, with the section cited |
| `repo` | In the authors' code, cited to `file.py:L40` |
| **[inferred]** | Supplied by the agent, with the assumption written out |
| `missing` | Not recoverable from any source |

Three things it does not do:

- **Download data.** It reads accession metadata only; the code refuses payload
  requests.
- **Run the analysis.** Notebooks ship unrun with empty outputs.
- **Install an analysis environment.** The notebook declares its own
  dependencies.

Example: [`EXAMPLE_protocol.md`](brew/output/EXAMPLE_protocol.md)

---

## forage — data discovery

```bash
cd forage
```

### Run the demo (no credentials)

```bash
./.venv/bin/python scripts/make_mock_inventory.py --out knowledge/inventory.mock.jsonl
./.venv/bin/python scripts/build_index.py --inventory knowledge/inventory.mock.jsonl
./.venv/bin/python scripts/search.py "<your research goal>" --limit 20
```

This builds a synthetic collection from `resources/metadata_example.csv` (40
fake requests). The mock tree re-roots paths, omits some requests, and includes
vague folder names the agent has to refuse rather than guess at.

To use your own data, add:

| File | Purpose |
| --- | --- |
| `resources/metadata.csv` | Your metadata export. Both scripts prefer it over the example when present. |
| `resources/project_codes.json` | Optional. Maps internal project codes to readable names. |

Both are gitignored.

### Connect to a real collection

Full setup is in [forage/README.md](forage/README.md#credentials-one-time).
Short version:

```bash
cp .claude/settings.json.example .claude/settings.json    # add your UUIDs
security add-generic-password -a "$USER" -s globus_agent_client_secret -w

globus endpoint permission create <COLLECTION_UUID>:/ \
    --identity <CLIENT_UUID>@clients.auth.globus.org --permissions r   # r, never rw

./.venv/bin/python scripts/verify_readonly.py <COLLECTION_UUID>
```

Then `claude` in the directory:

```
/forage <what data are you looking for?>
```

**Read-only comes from the collection permission, not the code.** Globus
Transfer has no read-only scope — it is `transfer.api.globus.org:all` or
nothing — so the limit has to come from what the client identity is allowed to
do. Never grant the client `rw` or an access-manager role.

A full scan takes about 3 hours at `--depth 5`. Reuse the cached inventory
unless the roots changed.

Examples: [`EXAMPLE_discovery_report.md`](forage/output/EXAMPLE_discovery_report.md)
and [`EXAMPLE_ASSOCIATIONS.md`](forage/knowledge/EXAMPLE_ASSOCIATIONS.md), both
produced by running the real pipeline against the mock collection.

---

## Connectors

Anthropic-hosted MCP connectors. Authorize them in your claude.ai connector
settings, or with `/mcp` in Claude Code — the repo cannot do it for you. Schemas
are deferred, so agents load them with `ToolSearch` when needed. If one isn't
authorized, the agent falls back to the open web and says so.

| Connector | Used by | Notes |
| --- | --- | --- |
| PubMed | brew | Citation → PMID → PMCID → full text. Only ~6M articles have PMC full text. |
| Scite | brew | Full-text excerpts for a passage, plus `editorialNotices` for retractions and corrections. Excerpts are open-access only. |
| bioRxiv | brew | `get_preprint` by DOI. Its search filters by date and category only — no keyword search, so it cannot find a preprint by name. |
| Clinical Trials | distill (optional) | ClinicalTrials.gov lookups |
| `WebSearch` / `WebFetch` | distill; brew as fallback | Built into Claude Code, no authorization needed |

Not used by any agent: Box, ChEMBL, Gmail, Google Calendar, Google Drive,
Microsoft 365, Zoom.

Globus is not an MCP connector. `forage` calls the Transfer API through
`globus-sdk`.

---

## What git tracks

Reports go to each agent's `output/` as Markdown and PDF. The Markdown is the
source of truth — regenerate the PDF rather than editing it.

[.gitignore](.gitignore) excludes:

| Excluded | Reason |
| --- | --- |
| everything in `output/` | Run history is local |
| `forage/knowledge/` | Scan stores reach ~900 MB, over GitHub's 100 MB limit |
| `brew/data/` | Downloaded public data, re-fetchable from the accession |
| `forage/.claude/settings.json` | Your Globus client and collection UUIDs. Copy `settings.json.example`. |
| `forage/resources/metadata.csv` | Real exports contain names and internal paths. `metadata_example.csv` ships instead. |
| `forage/resources/project_codes.json` | Internal project codes. `project_codes.example.json` ships instead. |
| venvs, `.env`, `*.secret`, `tokens.json` | — |

Client secrets go in the macOS Keychain. UUIDs come from environment variables,
and the agents are told never to write one into a report.

Seven sample files named `EXAMPLE_*` are committed as an explicit exception,
listed one by one in `.gitignore`. Each states in its first line that it is
synthetic. Do not rename a real run to `EXAMPLE_` — outputs can contain
unpublished results, and an earlier wildcard rule exposed exactly that.

---

## Limitations

- **Platform.** Built and tested on macOS. The PDF renderers look for Chrome,
  Chromium, Edge, and Brave both by path and on `PATH`, so Linux and Windows
  should work where one is installed. The `cupsfilter` fallback and the Keychain
  are macOS-only, and neither is required — `forage` reads
  `GLOBUS_AGENT_CLIENT_SECRET` from the environment when the Keychain is
  unavailable. Untested off macOS.
- **A metadata CSV covers only what the sequencing core recorded.** Assays with
  no request number — proteomics, imaging, EM, behavior, ephys — cannot appear
  in it. "Not in the CSV" does not mean "no data exists"; search the association
  store, which covers everything scanned.
- **`brew` does not run the analysis.** Notebooks ship unrun. Protocol
  checkpoints state what a correct run should produce.
- **`forage`'s inferred tier is a guess.** Anything attributed from folder names
  rather than a request record is unverified. The report labels it; confirm
  before relying on it.
- **The literature connectors are life-sciences databases.** Outside those
  fields, `brew` and `distill` use the open web and the source PDF.
