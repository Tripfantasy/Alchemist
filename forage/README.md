# Globus Discovery Agent

Takes a researcher's goals, scans a Globus collection read-only, and returns a
manifest of relevant files plus an honest account of what the data cannot
answer. Associations accumulate in `knowledge/` for a later
database-organization agent.

## Setup

```bash
cd forage
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Credentials (one time)

You have a confidential client. **Globus generates the secret — you do not
choose it.** On the client's page at <https://app.globus.org/settings/developers>,
click **Add Client Secret**, give it a *label* (e.g. `globus-agent-2026-08`),
and copy the generated value. It is displayed exactly once.

The developers.globus.org *project* UUID groups clients and their admins; it is
not used at runtime. Only the **client UUID** is.

```bash
export GLOBUS_AGENT_CLIENT_ID=<client-uuid>        # add to ~/.zshrc to persist

# store the secret in the Keychain (preferred over an env var, which every
# child process inherits and which tends to reach shell history)
security add-generic-password -a "$USER" -s globus_agent_client_secret -w
# paste the secret at the prompt -- it is read invisibly
```

`GLOBUS_AGENT_CLIENT_SECRET` is honoured as a fallback if you prefer env vars.

To rotate: add a second secret, confirm the agent still runs, then delete the
old one. Globus allows multiple live secrets per client, so there is no
downtime window.

### Grant the client READ-ONLY on the collection

This is the step that actually enforces read-only. The confidential client
authenticates as its own identity, distinct from your login:

```
<CLIENT_UUID>@clients.auth.globus.org
```

Grant that identity `r`, never `rw`:

```bash
globus endpoint permission create <GUEST_COLLECTION_UUID>:/ \
    --identity <CLIENT_UUID>@clients.auth.globus.org \
    --permissions r
```

Do **not** give the client an access-manager role — a client that can edit ACLs
can grant itself write access, which defeats the whole arrangement.

### Verify

```bash
./.venv/bin/python scripts/verify_readonly.py <COLLECTION_UUID>       # as the agent
globus endpoint permission list <COLLECTION_UUID>          # as the admin
```

Expect exactly one rule for the client identity, with permissions `r`.

## Invoking it

Three ways, in a fresh Claude Code session started in this directory:

```
/forage I need data on Ab42 in cerebral organoids
```

The `/forage` slash command (`.claude/commands/forage.md`) is the explicit
route. You can also just describe a goal in plain language — the
`globus-discovery` skill in `.claude/skills/` triggers on questions like "what
data do we already have on X?" — or simply say "follow workflows/data_discovery.md".

All three funnel to the same recipe, so there is one source of truth to edit.

`.claude/settings.json` sets `GLOBUS_AGENT_CLIENT_ID` for the session, so it
works regardless of which shell you use. **New sessions pick it up
automatically; a session already running when the file was created will not.**

## Run it by hand

Follow `workflows/data_discovery.md`. In short:

```bash
./.venv/bin/python scripts/scan_endpoint.py <UUID> --path /projects/yu/ --out knowledge/inventory.jsonl
./.venv/bin/python scripts/build_index.py --inventory knowledge/inventory.jsonl
./.venv/bin/python scripts/search.py "your research goal" --types omics,tabular --out knowledge/candidates.json
```

Then read `candidates.json`, apply judgment, and write the report from
`resources/report_template.md` into `output/`.

## Reports: .md + .pdf

Every report ships as both. The `.md` is the source of truth; the `.pdf` is
derived and safe to delete or regenerate.

```bash
./.venv/bin/python scripts/render_report.py output/some_report.md   # one
./.venv/bin/python scripts/render_report.py --all                   # everything stale
./.venv/bin/python scripts/render_report.py --all --force           # ignore mtime
./.venv/bin/python scripts/render_report.py report.md --keep-html   # keep intermediate
```

Renders via headless Chrome (already installed) with print CSS — real tables,
controlled page breaks, no LaTeX or `wkhtmltopdf` to install. Falls back to
macOS `cupsfilter` if no Chrome-family browser is found. Skips files whose PDF
is newer than the source unless `--force`.

Two authoring conventions:

- **Field lines** (`**Project:** ...` on consecutive lines) each keep their own
  line in the PDF — the renderer inserts hard breaks *before* each one, so a
  wrapped value can't swallow the next field.
- **A paragraph starting with ⚠️** becomes an amber caveat box.

## Try it without credentials

The whole pipeline runs against a synthetic tree built from the real metadata
CSV. The mock deliberately re-roots every path, drops some requests entirely,
and includes vague folders that must be refused rather than interpreted.

```bash
./.venv/bin/python scripts/make_mock_inventory.py --out knowledge/inventory.mock.jsonl
./.venv/bin/python scripts/build_index.py --inventory knowledge/inventory.mock.jsonl
./.venv/bin/python scripts/search.py "APOE4 vs APOE3 organoid gene regulatory networks" --limit 20
```

To reset the store: `rm knowledge/*.jsonl knowledge/*.json knowledge/*.md`

## Safety

Read-only is enforced in three layers, weakest to strongest.

**3. In-process guard.** `ReadOnlyTransferClient` in `scan_endpoint.py` raises
on 12 mutating methods (`submit_transfer`, `submit_delete`, `operation_mkdir`,
`operation_rename`, ACL changes). Stops accidents; does not stop anyone who
deletes the guard.

**2. Scope — unavailable, and worth knowing why.** Globus Transfer has **no
read-only scope**. It is `transfer.api.globus.org:all` or nothing, covering
reads and writes together. Read-only cannot come from scope selection.

**1. Collection permission — the real guarantee.** Because the scope cannot be
narrowed, restriction comes from what the *identity* may do. The confidential
client holds `r` on the guest collection, so Globus rejects writes server-side
regardless of what this code asks for. This is the layer that holds when the
others fail.

This is why a confidential client beats a Native App here: a Native App acts as
*you*, inheriting your write access, which collapses layer 1 and leaves the
guard as the only protection.

### Why verification never attempts a write

The obvious test — call `operation_mkdir`, assert it fails — creates a
directory on the collection whenever it *fails*. A check for "nothing is ever
created" must not create something in its failure mode. `verify_readonly.py`
reads the permission list instead: same answer, no side effects.

## Files

| path | role |
| --- | --- |
| `scripts/globus_auth.py` | confidential-client auth (Keychain secret), Native App fallback |
| `scripts/scan_endpoint.py` | recursive read-only walk → `inventory.jsonl` |
| `scripts/build_index.py` | CSV join + vocabulary inference → associations |
| `scripts/search.py` | lexical recall over the store → ranked candidates |
| `scripts/kb.py` | the only writer to `knowledge/`; supersession + fingerprints |
| `scripts/rollup.py` | bounded summary → `knowledge/ASSOCIATIONS.md` |
| `scripts/make_mock_inventory.py` | synthetic tree for testing without Globus |
| `scripts/render_report.py` | markdown report -> print-quality PDF |
| `scripts/verify_readonly.py` | proves read-only without writing anything |
| `resources/vocab.json` | editable term dictionary for path inference |
| `resources/metadata_example.csv` | 40 synthetic requests; replaced by `metadata.csv` (gitignored) if you supply one |
| `resources/project_codes.example.json` | optional code → project-name map; replaced by `project_codes.json` (gitignored) |
| `workflows/data_discovery.md` | **the recipe — single source of truth** |
| `.claude/commands/forage.md` | `/forage` slash command |
| `.claude/skills/globus-discovery/` | auto-trigger on data-discovery questions |
