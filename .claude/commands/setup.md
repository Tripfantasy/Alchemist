---
description: First-time setup - choose where forage reads data (Globus or a local folder) and set up sigil's lab profile
argument-hint: "[forage | sigil]  (default: both)"
---

Configure Alchemist for this person: forage's data source, then sigil's lab
profile. `$ARGUMENTS` may name one of them to set up only that part.

Setup configures; it never runs an agent. It scans nothing, opens no archive,
and touches no Globus collection.

## Rules for the whole command

- **Never ask for a UUID or the client secret in the chat**, and never print
  one. The person puts UUIDs in `forage/.claude/settings.json` and the secret in
  the Keychain themselves. `setup.py` reports them by name and status only.
- **Globus is left exactly as it is.** Choosing Globus writes only
  `"backend": "globus"`. It changes no permission, script, or rule, and never
  suggests granting the client `rw`.
- **`--allow-writable` is never part of setup.** It belongs to a local scan, and
  only with the researcher's approval in that run (forage/LOCAL.md).
- **The lab's description is the person's own words.** Save it verbatim (fix
  only obvious typos). Never write it for them, never fill it from the data.
- **Reconfiguring is opt-in.** Anything already configured stays as it is
  unless the person asks to change it.

## Step 1 — What is already configured

```bash
python3 .claude/lib/setup.py status
```

Show the result in a few lines. If both say CONFIGURED, say so and ask whether
they want to change anything (data source, roots, lab details). Stop if not.
Otherwise set up only what says NEEDS SETUP, in the order below.

## Step 2 — forage: where is the data?

Ask with AskUserQuestion:

- **Globus collection**: the data is on a Globus collection. Needs a Globus
  confidential client with read (`r`) access to it.
- **Local or mounted folder**: the data is reachable as a path on this machine
  (a NAS mount, a lab server, a local disk). No Globus account needed.
- **Skip forage for now.**

Then create forage's venv if status said MISSING:

```bash
python3 .claude/lib/setup.py venv forage
```

### If Globus

1. `python3 .claude/lib/setup.py backend globus`
2. If status showed the settings MISSING, tell them, as steps to do themselves
   **outside the chat**:
   - Copy `forage/.claude/settings.json.example` to
     `forage/.claude/settings.json` and fill in the two UUIDs in their editor.
   - Store the client secret in a terminal:
     `security add-generic-password -a "$USER" -s globus_agent_client_secret -w`
     (it prompts for the secret; nothing is echoed).
   - Grant the client `r` (never `rw`) on the collection in the Globus web app.
     forage/README.md, "Connect to a real collection", has the details.
   Wait until they say it is done, then run `status forage` again.
3. When the settings and secret show ok:
   ```bash
   python3 .claude/lib/agent_env.py sync
   python3 .claude/lib/agent_env.py check forage
   ```
   If `check` still fails after the sync, the session must be restarted to
   pick up the settings. Say so, and that `/setup` will continue from here.
4. Once `check` passes, verify the permission is read-only (it attempts no
   write):
   ```bash
   cd forage && ./.venv/bin/python scripts/verify_readonly.py "$GLOBUS_AGENT_COLLECTION_ID"
   ```
   If it reports write access, stop. forage must not be used until the client
   holds only `r`.

### If local

1. Ask in plain text which directories hold the data. Each becomes a root;
   forage may read only inside them. Suggest the narrowest directory that
   covers the data, not a whole disk or the home folder.
2. `python3 .claude/lib/setup.py backend local --root <dir> [--root <dir>]`
   (add `--label <name>` if the same mount will be scanned from more than one
   computer).
3. Check each root, without walking:
   ```bash
   cd forage && ./.venv/bin/python scripts/scan_local.py --check
   ```
   For any root marked **WRITABLE**, explain: on a local path nothing but the
   mount stops a write, so forage refuses to scan a root this account can write
   to. Recommend a read-only mount (`forage/LOCAL.md` shows one). Do not offer
   `--allow-writable` here.
4. Say what the local backend changes: forage reads `forage/LOCAL.md` on
   every run from now on, and Globus credentials are not needed.

### Optional site files (either backend)

Mention, without asking each as a question, that forage works with defaults
and improves with three optional files, all gitignored, explained in
forage/README.md: `resources/metadata.csv` (the sequencing core's request
export), the request-ID format in `resources/site.json`, and
`resources/vocab.json` (copy `vocab.example.json` and grow it).

## Step 3 — sigil: the lab's details

If status said NEEDS SETUP for sigil, create its venv if it showed MISSING
(`python3 .claude/lib/setup.py venv sigil`; the PDF renderer needs it). If any
lab detail showed MISSING, ask in plain text, not as a multiple-choice
question, because only the person can answer:

> For sigil's lab profile:
> 1. In two or three sentences, what is the lab's focus?
> 2. What name should the profile use for the lab?
> 3. The PI's name as it appears on papers, their current institution, and
>    any prior institution the lab's papers came from.
> 4. The PI's ORCID, if they have one.

Write their answers (shape as in sigil/workflows/lab_profile.md, Step 2):

```bash
python3 .claude/lib/setup.py lab <<'EOF'
{"name": "...", "description": "...",
 "pi": {"name": "...", "pubmed_author": "Lastname Initials",
        "institutions": ["current", "prior"], "orcid": "..."}}
EOF
```

Theme groups and term merges are not set up here: sigil proposes them from the
data on its first run, and the person confirms them there.

## Step 4 — Wrap up

Run `python3 .claude/lib/setup.py status` once more and report it. Then give
the next command:

- forage configured: `/forage <a research goal>`. The first run surveys the
  data before any scan.
- sigil needs a forage snapshot first: `/sigil` after at least one forage scan.
- Bias reporting is asked by each agent at the start of its first run.
