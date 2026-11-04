# Workflow: Lab Profile

Turn what forage has learned about the lab's data collection into a profile a
new lab member or a collaborator can read in ten minutes: what the lab works
on, how it approaches those questions, which methods and tools it uses, and
what data exists.

Regenerated on demand. Nothing here updates on its own after a forage run.

**Hard rules, no exceptions:**

- **Read-only on everything outside `sigil/`.** sigil reads forage's exported
  snapshot and nothing else of forage's. It never touches the knowledge store,
  never scans, never talks to Globus.
- **Soft truth, plainly stated.** The profile's readers want to know what
  research the lab does and what data is available, not how each fact was
  derived. Request records and folder-name inferences are both presented as
  what the lab does: no tier badges, no "inferred" labels, no hedging, no
  scope disclaimers. (This is a decision about sigil's audience. forage keeps
  the distinction internally and in its own reports, where search and gap
  analysis depend on it.)
- **Every number comes from the data files.** Soft truth is about wording, not
  invention: nothing in the prose that the JSON does not support.
- **Two editions, always.** The internal edition may name paths, request IDs
  and people, and includes the Exploration view of forage's progress. The
  collaborator edition names none of them and has no Exploration view. It is
  never shared before the researcher has reviewed it (Step 8).
- **Nothing leaves the machine.** The only outbound request is the PubMed
  search in Step 3, which sends the PI's public identifiers and nothing about
  the collection. Outputs stay in `sigil/output/` (gitignored).
  Never publish a dashboard or profile as a hosted page or upload it anywhere:
  the internal edition carries site details. The researcher shares files
  themselves.

---

## Step 0 — The bias-reporting question (separate, and additional)

Asked once per session, before intake. **It does not use an intake slot.**
Separate `AskUserQuestion` call, one question; Step 4 still gets its full round.

```bash
python3 ../bias/report.py status --session <session-id>
```

- **`asked already : yes`** — don't ask again; use the reported state.
- **`asked already : NO`** — ask:

> Enable bias reporting for this session?
> - **No** — the default. Profiles carry no influence section
> - **Yes** — each profile gains a *Context & Influence* section listing what shaped it besides your request, and runs accumulate in `bias/log.jsonl` for a cross-run view

Record the answer yourself — **never ask the user to run a command**:

```bash
python3 ../bias/report.py set --enabled true|false --session <session-id>
```

No session id available? Use "have I already asked in this conversation?" as the
test.

## Step 1 — Check the snapshot (local, before intake)

The profile is only as current as forage's snapshot. Check it before asking
anything, because the intake options come from it:

```bash
python3 -c "
import json, pathlib
p = pathlib.Path('../forage/knowledge/snapshot.json')
if not p.exists(): print('NO SNAPSHOT'); raise SystemExit
s = json.loads(p.read_text())
print('generated :', s['generated'])
print('files     :', s['store']['files'])
print('themes    :', sorted({r['project'] or 'Unassigned' for r in s['requests']}))"
```

- **No snapshot, or older than the newest forage run** (compare with the last
  `ts` in `../forage/knowledge/query_log.jsonl`): export one. This is local,
  read-only on the store, and takes a minute or two:

  ```bash
  ../forage/.venv/bin/python ../forage/scripts/export_snapshot.py
  ```

  Say that you are doing it. It is forage's script, run with forage's
  interpreter; sigil does not reimplement it.
- **Snapshot current:** reuse it.

Never trigger a forage *scan* from here. If the snapshot is too thin to profile
the lab (one scanned folder, say), say so and hand back the `/forage` command.

## Step 2 — The lab's own details (first run only)

`resources/lab.json` (gitignored) holds the lab's display name, a short
description in the researcher's own words, and the PI's identifiers for the
publications list. It opens both the dashboard and the profile.

- **It does not exist** (the first run): before the intake round, ask in plain
  text, not as a multiple-choice question, because only the researcher can
  answer:

  > Before I build the profile:
  > 1. In two or three sentences, what is the lab's focus?
  > 2. What name should the profile use for the lab?
  > 3. The PI's name as it appears on papers, their current institution, and
  >    any prior institution the lab's papers came from.
  > 4. The PI's ORCID, if they have one.

  Save the description verbatim (fix only obvious typos). Do not embellish it
  from the data; the data gets its say in the profile itself. Shape:

  ```json
  {"name": "...", "description": "...",
   "pi": {"name": "...", "pubmed_author": "Lastname Initials",
          "institutions": ["current", "prior"], "orcid": "0000-..."}}
  ```
- **It exists:** show the name, description and PI in one line each, and ask,
  as one option in the Step 4 round, whether they still hold. Update if not.

## Step 3 — Recent publications (every run)

The five most recent papers that are **the lab's own work**, fetched fresh from
PubMed with the PubMed connector (load it with `ToolSearch`). If the connector
is not authorized, say so and keep the list already in `lab.json`; never fill
it from memory.

**Search.** ORCID tagging and affiliations are both incomplete in PubMed, so
union two queries, sorted by publication date:

- `<orcid>[auid]`
- `<pubmed_author>[Author] AND ("<institution 1>"[Affiliation] OR "<institution 2>"[Affiliation] ...)`

Fetch metadata for the candidates and keep a paper only if **all** of these hold:

1. **The PI is first or last author.** A paper where the PI sits in the middle
   of another institution's author list is a collaboration, not lab work.
2. **The PI's own affiliation on that paper** names one of the lab's
   institutions.
3. **It is research, a methods paper or a review.** Exclude editorials,
   commentaries, historical articles, essays, news, letters and published
   errata.
4. **It is not a preprint of a paper that is also listed.** Keep the journal
   version; keep a preprint only if no published version exists.

Take the five most recent. **On the first run, show them to the researcher
with their DOI links and what was excluded and why, and save only after they
confirm.** On later runs, save and list them in the hand-back. Write them to
`lab.json` as `publications` (pmid, doi, year, month, title, journal, authors
as "Lastname Initials" in order, type) with `publications_fetched` set to
today. They are public, so both editions show them, always with their DOI
links and a PubMed credit, as PubMed's terms require.

## Step 3b — Group themes and merge terms (first run; then only what is new)

Raw request themes are whatever people typed into the core's form: near
duplicates ("Regeneration", "Regenration"), project nicknames, even a
person's name. Readers need a handful of broad themes. Likewise the
vocabulary can list a cell type beside the tissue it lives in.

- **Propose broad themes** from the raw theme names *and* each request's
  Analysis Goals and title (in `../forage/resources/metadata.csv`, which this
  step may read). Think broad: three to six themes for most labs. Flag requests
  that look misfiled, by ID and with the reason, as candidate overrides.
- **Propose term merges** where the tissue view would split one structure:
  a cell type into its tissue, a synonym into its main term.
- Show both as tables, ask once, and save the confirmed versions to
  `resources/lab.json` as `theme_groups` (broad theme -> raw themes),
  `request_themes` (request ID -> broad theme) and `term_merges`.
- **Later runs:** the build prints any raw theme not in a group. Propose a home
  for just those; never re-ask the whole grouping.

## Step 4 — Intake (one round, options from the snapshot)

1. **Themes to keep out of the collaborator edition.** List the actual theme
   names from the request records (multi-select). Themes with fewer than two
   requests fold into "Other" automatically; this question is for themes that
   name unpublished work, a person, or an internal code. *Why it matters:* the
   collaborator edition goes outside the lab.
2. **What to lead with.** The research themes, the methods, or the biology.
   Changes the order and emphasis of the written profile, not the dashboard.
3. **The lab's details** (only when `resources/lab.json` already exists):
   keep the name, description and PI, or update them.

Never fill these from the "About Me" block, from past profiles in `output/`, or
from earlier turns. A profile that silently reuses last month's hidden-theme
list leaks whatever was added since.

## Step 5 — Build the data and dashboards

```bash
python3 scripts/build_profile.py --hide-theme "<theme>" --hide-theme "<theme>"
```

Writes to `output/`: `profile_data_<date>.json` (internal),
`profile_data_<date>_collab.json`, and the two dashboards. Stdlib only; any
python3 runs it, offline. The lab's name, description and publications come
from `resources/lab.json`.

Read the "themes not in any group" and "unmapped terms" lines it prints
(see Step 3b). A term that matters to this lab but
maps to no family is a gap in `resources/families.json`. Offer to add it;
never quietly drop it.

## Step 6 — Write the two profiles

Read `resources/profile_template.md`. Write:

- `output/lab_profile_<date>.md` from `profile_data_<date>.json`
- `output/lab_profile_<date>_collab.md` from `profile_data_<date>_collab.json`

Rules for the prose:

- **Open with the lab's own description**, verbatim, then build on it.
- **Every number comes from the JSON.** Do not count anything yourself. If a
  sentence needs a number the JSON does not have, drop the sentence.
- **Write for someone on their first week.** Plain words, short sections,
  bullets over paragraphs. Expand every abbreviation once. Explain what a
  "project folder" is the first time it appears.
- **State it plainly.** "The lab uses patch-clamp electrophysiology on
  cardiomyocytes", not "folder names suggest". No ⚠️ caveats, no tier labels,
  no scope paragraph.
- **Describe approaches, not inventories.** "Regeneration questions are
  attacked mostly with bulk and single-cell RNA-seq, with spatial
  transcriptomics added for ..." beats a list of counts. The dashboard has the
  counts.
- **Both editions list the recent publications** with DOI links and "From
  PubMed".
- **The internal edition ends with Exploration**: what forage has catalogued
  so far, in a short paragraph. The collaborator edition has no such section.
- **The collaborator edition is written from the collaborator JSON only.** It
  never mentions a path, request ID, request title, requester, or a folder
  named after a person, even in passing, even if the internal JSON is open.

Then render both:

```bash
./.venv/bin/python scripts/render_report.py output/lab_profile_<date>.md
./.venv/bin/python scripts/render_report.py output/lab_profile_<date>_collab.md
```

## Step 7 — Look at the dashboards

Open or screenshot both HTML files before handing them back. Check that every
view rendered, labels do not collide, and the collaborator edition shows no
folder paths, request IDs, names or Exploration view. A view that is empty for
this lab should say so on the page, not disappear.

## Step 8 — Hand back, with the collaborator review

Report the six files and what each is for. Then show the researcher what the
collaborator edition exposes, in one short list: the theme names it shows, and
the most prominent words in its word cloud. Ask whether anything there should
not leave the lab. If so, re-run Step 5 with `--hide-theme`, or extend
`families.json`, and regenerate. Never treat silence as approval to share.

## Step 9 — Bias log (if enabled in Step 0)

Append a **Context & Influence** section to the internal profile and log the run:

```bash
python3 ../bias/report.py append --file <scratchpad>/bias_run.json
```

Format and record shape are in `../bias/README.md`, with `"agent": "sigil"`.
The influences that matter here:

- **`knowledge_store`** — sigil is built entirely on forage's accumulated store,
  which reflects what past questions caused forage to scan.
- **`vocab`** — the site vocabulary decides which folder names become facts in
  the profile. Under soft truth, a misread term is presented as fact, so log
  any that look wrong.
- **`local_file`** — `resources/lab.json`, when reused from an earlier run
  rather than written in this one.
- **`prior_output`** — log it if a previous profile was read for any reason.
