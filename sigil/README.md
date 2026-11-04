# sigil — lab profile

Turns what `forage` knows about the lab's data collection into something a new
lab member or a collaborator can digest in ten minutes:

- **A written profile** (`.md` + `.pdf`): opens with the lab's own description,
  then research themes and how each is approached, methods beyond sequencing,
  biological focus and toolkit.
- **An interactive dashboard** (`.html`): a clickable word cloud of the lab's
  vocabulary that filters the charts below it, the research views, and (internal
  edition) an Exploration view of forage's progress: a zoomable map of how the
  collection's files and storage are spread across folders, and the growth of
  the catalogue and of questions answered over time. Hover details, a table view under every
  chart, and a Dark mode switch. One self-contained file: it opens offline and
  can be attached to an email.

Both come in two editions on every run. The **internal** edition names paths,
request IDs and people. The **collaborator** edition names none of them, folds
small or hidden themes into "Other", leaves out the Exploration view, and is
reviewed before it is shared.

The profile states what the lab does plainly. Facts from the sequencing core's
request records and facts read from folder names are presented alike, without
labels or hedging: readers want the research and the data, not the provenance.
forage keeps that distinction in its own store and reports.

Regenerated on demand. Nothing updates on its own.

## Setup

```bash
cd sigil
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

`build_profile.py` is stdlib-only. The venv is for the PDF renderer's
`markdown` dependency. No credentials: sigil never talks to Globus.

## Invoking it

In a session opened in `sigil/`, or from the repo root:

```
/sigil
/sigil lead with the methods, this is for a lab-meeting talk
```

It asks the bias question and checks forage's snapshot. On the first run it
asks you to describe the lab's focus in a few sentences, name it, and give the
PI's name, institutions (current and prior) and ORCID. That is saved to
`resources/lab.json` (gitignored) and reused, with an offer to update.

The core's raw theme names are often near-duplicates, nicknames or a person's
name. On the first run sigil proposes a handful of broad themes from those
names and each request's goals, flags requests that look misfiled, and
suggests merging overlapping vocabulary (a cell type into its tissue). You
confirm; it saves them to `lab.json`, and later runs ask only about new themes.

Each run then fetches the lab's five most recent papers from PubMed: papers
where the PI is first or last author with one of the lab's institutions, with
editorials, essays, errata and preprint duplicates left out. The first time,
you confirm the list before it is saved. The search is the only outbound
request sigil makes, and it sends only the PI's public identifiers.
Then one intake round (which themes to keep out of the collaborator edition,
what to lead with) before building anything.

## Where the data comes from

sigil reads exactly one thing it does not own: `forage/knowledge/snapshot.json`,
an aggregated export that forage writes with its own script:

```bash
cd ../forage && ./.venv/bin/python scripts/export_snapshot.py
```

The snapshot holds counts per request and per project folder, never per file.
If it is missing or older than forage's latest run, sigil runs that exporter
for you. It never runs a forage scan: a profile reflects what forage has
already scanned, and the dashboard says so at the top.

## The views

| View | Answers |
| --- | --- |
| The lab at a glance (word cloud) | The lab's most common tissues, methods, models and tools. Click a word for what it goes with; it highlights in every chart |
| Research themes and how they are approached | Which sequencing approaches each theme uses |
| Methods beyond sequencing | Physiology, imaging, behavior, proteomics, and on which tissues |
| Biological focus | Tissue × developmental stage or timepoint; conditions; organisms |
| Toolkit | Genetic tools (reporters, drivers, indicators) and analysis languages |
| Recent publications | The lab's five most recent papers from PubMed, with DOI links |
| Exploration (internal only) | What forage is for, how much it has catalogued, a zoomable folder map (by files or storage), and how the catalogue and questions answered grew |

Views count **project folders**, not files: a directory three levels below the
top of the collection (forage's `--unit-depth`). Counting files would let one
instrument writing a file per channel dominate every chart.

Specific assay names never reach a chart: `resources/families.json` maps them to families such as "Behavior" or
"Electrophysiology". Terms that map to no family are printed after each build
and listed in the profile's appendix, so a missing mapping is visible.

## Run it by hand

```bash
python3 scripts/build_profile.py --hide-theme "Unpublished thing"
./.venv/bin/python scripts/render_report.py output/lab_profile_<date>.md
```

`build_profile.py` writes the data files and both dashboards. The written
profiles are authored from the data files, per `workflows/lab_profile.md`.

## Files

| path | role |
| --- | --- |
| `workflows/lab_profile.md` | **the recipe — single source of truth** |
| `scripts/build_profile.py` | snapshot → `profile_data_*.json` + both dashboards |
| `scripts/render_report.py` | markdown profile → PDF |
| `resources/families.json` | term → family mappings (methods, stages, tools, languages) |
| `resources/dashboard_template.html` | the dashboard: validated colour tokens, inline script |
| `resources/profile_template.md` | the written profile's structure |
| `resources/lab.json` | local only (gitignored): the lab's name, description, PI identifiers, recent publications, broad themes and term merges |
| `output/EXAMPLE_*` | synthetic examples built from forage's mock collection |
