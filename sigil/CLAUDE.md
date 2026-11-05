# Project Context

sigil turns what the lab's data collection says about its work into a profile
that a new lab member or a collaborator can digest: research themes and how
they are approached, methods, biological focus, toolkit, a word cloud of the
lab's vocabulary, and (internal edition) forage's progress mapping the data.
It ships as a written profile (.md + .pdf) and an interactive dashboard
(.html), each in an internal and a collaborator edition.

# Rules

- Always ask clarifying questions before starting a complex task.
- Show your plan and steps before executing.
- Keep the profile digestible: plain words, bullets over paragraphs, every
  abbreviation expanded once.
- Save all output files to the output folder.
- READ-ONLY outside sigil/. sigil reads exactly one thing it does not own:
  forage's exported snapshot, ../forage/knowledge/snapshot.json. Never read
  forage's JSONL stores, never import forage's code, never scan, never touch
  Globus. Producing a fresh snapshot means running forage's own exporter with
  forage's interpreter (workflow Step 1), not reimplementing it.
- SOFT TRUTH, PLAINLY STATED. Readers want to know what research the lab does
  and what data exists, not how each fact was derived. Request records and
  folder-name inferences are both presented as what the lab does: no tier
  badges, no hedging, no scope disclaimers. This is a decision about sigil's
  audience only; forage keeps the distinction in its own store and reports.
  Soft truth is about wording, never invention: every number comes from the
  data files.
- Two editions every run. The collaborator edition contains no paths, request
  IDs, request titles, requester names, folders named after people, or
  Exploration view. Its mouse-line tab shows only lines with a public
  repository stock; in-house and unpublished lines are internal only. It is reviewed by the researcher before it is shared.
- The lab's description is the researcher's own words, asked for on the first
  run and kept in resources/lab.json (gitignored). Never write it for them.
- Broad themes, misfiled-request overrides and term merges are the lab's own
  taxonomy: proposed by the agent, confirmed by the researcher, kept in
  lab.json. Never ship them, and never apply an unconfirmed one.
- Nothing leaves the machine. Never publish a profile or dashboard as a hosted
  page or upload it; the researcher shares files themselves. The one outbound
  request is the PubMed search for the lab's recent publications (workflow
  Step 3), which sends only the PI's public identifiers.
- Publications are the lab's own work: PI first or last author, PI's
  affiliation one of the lab's institutions, no editorials or essays, no
  preprint duplicates. Never list one PubMed did not return; always with its
  DOI link and a PubMed credit.
- Every report ships as BOTH .md and .pdf. Write the .md, then run
  `./.venv/bin/python scripts/render_report.py output/<name>.md`. The .md is the
  source of truth; the .pdf is derived - never hand-edit it, regenerate it.

# Site notes

Facts about one specific lab live in `CLAUDE.local.md` beside this file
(gitignored). Claude Code loads it automatically; a delegated run must read it
explicitly. Nothing site-specific belongs in this file.

# Invoking the workflow

`/sigil` runs it, or ask for a lab profile and the `lab-profile` skill
triggers. Both route to workflows/lab_profile.md, the single source of truth -
read it, do not work from memory.

# Environment

- `scripts/build_profile.py` is stdlib-only and runs under any python3.
- `scripts/render_report.py` needs `markdown`, installed only in the venv:
  `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt`
- PDF rendering needs a Chrome-family browser, found by path or on PATH.

# Project Structure

- workflows/ - the recipe (lab_profile.md)
- scripts/ - build_profile.py (snapshot -> data + dashboards), render_report.py
- resources/ - families.json (term -> family mappings), dashboard_template.html,
  profile_template.md, lab.json (local only: the lab's name, description, PI
  identifiers and recent publications)
- output/ - generated profiles and dashboards. Gitignored except the EXAMPLE_
  files built from forage's mock collection.

# Data contract

The snapshot is forage's interface, schema 1 or 2 (`"kind": "forage_snapshot"`;
2 adds `mouse_lines`: per line, folders named with it, the lines it shares
them with, its class, target, colony status and whether it is public). It
holds aggregates only: per request, per project folder (`unit_depth` path
segments), tier splits, term counts, and coverage (scans, opened and unopened
archives). If the schema changes, forage bumps `schema` and build_profile.py
refuses an unknown one rather than guessing.
