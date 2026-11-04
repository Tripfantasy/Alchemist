"""Build the lab-profile data and the interactive dashboards from a forage snapshot.

Reads forage's exported snapshot (forage/knowledge/snapshot.json, written by
forage/scripts/export_snapshot.py) -- never forage's stores directly. Writes,
into sigil/output/:

  profile_data_<date>.json          internal aggregates (paths, request IDs)
  profile_data_<date>_collab.json   collaborator aggregates
  dashboard_<date>.html             internal interactive dashboard
  dashboard_<date>_collab.html      collaborator dashboard

The written profile (.md/.pdf) is authored by the agent from the JSON files,
per workflows/lab_profile.md. This script does the counting, so every number
in the prose is traceable to a file on disk.

The lab's name and description come from resources/lab.json (gitignored,
written on the first run from the researcher's own words), or from
--lab-name / --lab-description.

Stdlib only. Each dashboard is ONE self-contained HTML file: data, styles and
script inline, no network requests, so it opens offline and can be attached.

Usage
-----
  python3 scripts/build_profile.py
  python3 scripts/build_profile.py --hide-theme "Theme X" --min-theme-requests 3
"""

import argparse
import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = ROOT.parent / "forage" / "knowledge" / "snapshot.json"
FAMILIES = ROOT / "resources" / "families.json"
TEMPLATE = ROOT / "resources" / "dashboard_template.html"
LAB_FILE = ROOT / "resources" / "lab.json"
OUT = ROOT / "output"
ZIP_SEP = ".zip!/"
OTHER = "Other"
CLOUD_TERMS = 60
TREE_CHILDREN = 10

BIOLOGY, METHODS, MODELS = "Biology", "Methods", "Models & tools"


# --------------------------------------------------------------------------
# term -> family mapping


def _rx(words):
    return re.compile("|".join(r"\b" + re.escape(w.lower()) for w in words))


class Families:
    def __init__(self, data: dict):
        self.approaches = [(re.compile(p, re.I), name) for p, name in data["sequencing_approaches"]]
        self.methods = [(name, _rx(words)) for name, words in data["methods"].items()]
        self.method_names = set(data["methods"])
        self.seq_words = [w.lower() for w in data["sequencing_assay_words"]]
        self.stages = [(re.compile(p, re.I), name) for p, name in data["stage_bands"]]
        self.stage_order = []
        for _, name in data["stage_bands"]:
            if name not in self.stage_order:
                self.stage_order.append(name)
        self.tools = [(name, _rx(words)) for name, words in data["tool_classes"].items()]
        self.languages = {name: set(exts) for name, exts in data["languages"].items()}

    def approach(self, project_type: str) -> str:
        for rx, name in self.approaches:
            if rx.search(project_type or ""):
                return name
        return OTHER

    def method(self, assay: str):
        low = assay.lower()
        if any(w in low for w in self.seq_words):
            return "__sequencing__"
        for name, rx in self.methods:
            if rx.search(low):
                return name
        return None

    def stage(self, term: str):
        for rx, name in self.stages:
            if rx.search(term):
                return name
        return None

    def tool(self, gene: str):
        low = gene.lower()
        for name, rx in self.tools:
            if rx.search(low):
                return name
        return None


# --------------------------------------------------------------------------
# per-unit reading


class SiteRules:
    """Lab-specific grouping from resources/lab.json (gitignored).

    theme_groups:   broad theme -> the raw request themes it gathers
    request_themes: per-request override, applied first (misfiled work)
    term_merges:    term -> canonical term (cell types into tissues, synonyms)
    """

    def __init__(self, lab: dict):
        self.group_of = {}
        for broad, raws in (lab.get("theme_groups") or {}).items():
            for raw in raws:
                self.group_of[raw.strip().lower()] = broad
        self.request_theme = {k: v for k, v in (lab.get("request_themes") or {}).items() if not k.startswith("_")}
        self.merge = {k.lower(): v for k, v in (lab.get("term_merges") or {}).items() if not k.startswith("_")}

    def theme(self, request_id: str, raw: str) -> str:
        if request_id in self.request_theme:
            return self.request_theme[request_id]
        return self.group_of.get((raw or "").strip().lower(), raw or "Unassigned")

    def term(self, t: str) -> str:
        return self.merge.get(t.lower(), t)


def interpretable(unit: dict) -> bool:
    t = unit.get("by_tier", {})
    return bool(t.get("csv") or t.get("inferred"))


def unit_terms(u: dict, fam: Families, approach_of_request: dict, unmatched, site) -> dict:
    """Everything one project folder says about the lab, already grouped."""
    terms = u.get("terms", {})
    methods = set()
    for a in terms.get("assay", {}):
        m = fam.method(a)
        if m is None:
            unmatched["assay"][a] += 1
        elif m != "__sequencing__":
            methods.add(m)
    for rid in u.get("requests", {}):
        if approach_of_request.get(rid, OTHER) != OTHER:
            methods.add(approach_of_request[rid])
    stages = set()
    for s in terms.get("stage", {}):
        band = fam.stage(s)
        if band:
            stages.add(band)
        else:
            unmatched["stage"][s] += 1
    return {
        "tissues": {site.term(t) for t in terms.get("tissue", {})},
        "methods": methods,
        "stages": stages,
        "species": {re.sub(r"\s*\(.*\)$", "", s) for s in terms.get("species", {})},
        "conditions": {site.term(c) for c in terms.get("condition", {})},
        "tools": {site.term(g): fam.tool(g) for g in terms.get("gene", {}) if fam.tool(g)},
    }


def build_tree(units: list) -> dict:
    """The collection as a folder tree (top level / subfolder / project folder).

    Each node carries its file count and its size in bytes, so the map can
    show either. Children past TREE_CHILDREN fold into one "+ N more" node so
    the embedded data stays small.
    """
    root = {"name": "Collection", "files": 0, "bytes": 0, "kids": {}}
    for u in units:
        segs = [s for s in u["path"].split("/") if s][:3] or ["(root)"]
        node = root
        node["files"] += u["files"]
        node["bytes"] += u["bytes"]
        for seg in segs:
            node = node["kids"].setdefault(seg, {"name": seg, "files": 0, "bytes": 0, "kids": {}})
            node["files"] += u["files"]
            node["bytes"] += u["bytes"]

    def finish(node):
        kids = sorted(node["kids"].values(), key=lambda k: -k["files"])
        shown, rest = kids[:TREE_CHILDREN], kids[TREE_CHILDREN:]
        out = {"n": node["name"], "f": node["files"], "b": node["bytes"]}
        children = [finish(k) for k in shown]
        if rest:
            children.append({"n": "+ {} more".format(len(rest)),
                             "f": sum(k["files"] for k in rest),
                             "b": sum(k["bytes"] for k in rest), "more": True})
        if children:
            out["c"] = children
        return out

    return finish(root)


# --------------------------------------------------------------------------
# aggregation


def aggregate(snap: dict, fam: Families, top: int, site: "SiteRules") -> dict:
    units = snap["units"]
    requests = snap["requests"]
    informative = [u for u in units if interpretable(u)]
    approach_of_request = {r["id"]: fam.approach(r["project_type"]) for r in requests}
    unmatched = defaultdict(Counter)

    # -- themes x sequencing approaches (request records)
    theme_of = {r["id"]: site.theme(r["id"], r["project"]) for r in requests}
    ungrouped = sorted({r["project"] for r in requests
                        if r["project"] and r["id"] not in site.request_theme
                        and r["project"].strip().lower() not in site.group_of})
    themes_count = Counter(theme_of.values())
    approaches = Counter(approach_of_request.values())
    cells = defaultdict(list)
    for r in requests:
        cells[(theme_of[r["id"]], approach_of_request[r["id"]])].append(r)

    # -- per-folder terms: methods, focus, toolkit, word cloud
    method_units, method_tissues = Counter(), defaultdict(Counter)
    tissue_units, tissue_stage, tissue_staged = Counter(), defaultdict(Counter), Counter()
    condition_units, species_units = Counter(), Counter()
    tool_units, tool_class = Counter(), {}
    lang_units = Counter()
    cloud, cloud_cat = Counter(), {}
    cooc = defaultdict(Counter)
    examples = defaultdict(list)
    for u in informative:
        t = unit_terms(u, fam, approach_of_request, unmatched, site)
        for m in t["methods"] & fam.method_names:
            method_units[m] += 1
            for tis in t["tissues"]:
                method_tissues[m][tis] += 1
        for tis in t["tissues"]:
            tissue_units[tis] += 1
            if t["stages"]:
                tissue_staged[tis] += 1
            for b in t["stages"]:
                tissue_stage[tis][b] += 1
        for c in t["conditions"]:
            condition_units[c] += 1
        for s in t["species"]:
            species_units[s] += 1
        for g, cls in t["tools"].items():
            tool_units[g] += 1
            tool_class[g] = cls
        exts = set(u.get("ext", {}))
        for lang, lex in fam.languages.items():
            if exts & lex:
                lang_units[lang] += 1

        labels = {(BIOLOGY, x) for x in t["tissues"] | t["stages"] | t["species"]}
        labels |= {(METHODS, x) for x in t["methods"]}
        labels |= {(MODELS, x) for x in t["conditions"] | set(t["tools"])}
        for cat, x in labels:
            cloud[x] += 1
            cloud_cat.setdefault(x, cat)
            if len(examples[x]) < 3:
                examples[x].append(u["path"])
        for (_, a), (_, b) in combinations(sorted(labels), 2):
            cooc[a][b] += 1
            cooc[b][a] += 1

    cloud_terms = [{"t": x, "cat": cloud_cat[x], "n": n,
                    "with": [w for w, _ in cooc[x].most_common(5)],
                    "eg": examples[x]}
                   for x, n in cloud.most_common(CLOUD_TERMS)]

    # -- exploration: forage's progress (internal edition only)
    hist = snap.get("history", {})
    cov = snap["coverage"]
    opened, unopened = len(cov["archives_listed"]), len(cov["archives_unopened"])
    runs = hist.get("runs", [])
    added = {d: sum(c.values()) for d, c in hist.get("first_seen", {}).items()}
    asked = defaultdict(list)
    for r in runs:
        asked[r["date"]].append({"goal": r["goal"], "kind": r["kind"]})
    explored = {}
    for e in hist.get("exploration", []):        # last scan of a day wins
        explored[e["date"]] = e
    growth, questions_total, cur = [], 0, None
    for d in sorted(set(explored) | set(asked)):
        if d in explored:
            cur = explored[d]
        questions_total += len(asked.get(d, []))
        growth.append({"date": d,
                       "explored": round(100.0 * cur["opened"] / cur["known"], 1) if cur and cur["known"] else None,
                       "opened": cur["opened"] if cur else None, "known": cur["known"] if cur else None,
                       "scanned": d in explored,
                       "questions": questions_total, "asked": asked.get(d, [])})
    exploration = {
        "files": snap["store"]["files"],
        "bytes": sum(snap["store"].get("bytes_by_tier", {}).values()),
        "folders": len(units),
        "folders_known": cur["known"] if cur else 0,
        "folders_opened": cur["opened"] if cur else 0,
        "questions": len(runs),
        "archives_opened": opened,
        "archives_total": opened + unopened,
        "tree": build_tree(units),
        "growth": growth,
    }

    # Only tissues some folder pairs with a stage or timepoint: a row of empty
    # cells says nothing. Ranked by how many folders make that pairing.
    top_tissues = [t for t, _ in tissue_staged.most_common(top)]
    return {
        "generated": snap["generated"],
        "kpis": {
            "themes": len([t for t in themes_count if t != "Unassigned"]),
            "requests": len(requests),
            "project_folders": len(informative),
            "methods": len(method_units) + len([a for a in approaches if a != OTHER]),
            "files": snap["store"]["files"],
        },
        "cloud": cloud_terms,
        "themes": {
            "rows": [t for t, _ in themes_count.most_common()],
            "cols": [a for a, _ in approaches.most_common()],
            "cells": {"{}|{}".format(t, a): [
                {"id": r["id"], "title": r["title"], "type": r["project_type"],
                 "on_collection": r["files_on_endpoint"]} for r in rs]
                for (t, a), rs in cells.items()},
            "row_totals": dict(themes_count), "col_totals": dict(approaches),
        },
        "methods": [{"name": m, "units": n,
                     "tissues": [t for t, _ in method_tissues[m].most_common(3)]}
                    for m, n in method_units.most_common()],
        "focus": {
            "tissues": top_tissues,
            "stages": fam.stage_order,
            "cells": {t: dict(tissue_stage[t]) for t in top_tissues},
            "tissue_units": {t: tissue_units[t] for t in top_tissues},
            "conditions": condition_units.most_common(top),
            "species": species_units.most_common(5),
        },
        "toolkit": {
            "tools": [{"name": g, "class": tool_class[g], "units": n}
                      for g, n in tool_units.most_common(top)],
            "languages": lang_units.most_common(),
        },
        "exploration": exploration,
        "unmatched": {k: v.most_common(25) for k, v in unmatched.items()},
        "ungrouped_themes": ungrouped,
    }


def redact(agg: dict, hide_themes, min_theme: int) -> dict:
    """The collaborator edition: the research, none of the plumbing.

    No paths, request IDs, titles or names, and no Exploration view (forage's
    progress is internal). Themes below min_theme requests, unassigned, or
    named in --hide-theme fold into 'Other'.
    """
    hide = {h.lower() for h in hide_themes}
    th = agg["themes"]
    keep = [t for t in th["rows"]
            if th["row_totals"][t] >= min_theme and t.lower() not in hide and t != "Unassigned"]
    rename = {t: (t if t in keep else OTHER) for t in th["rows"]}
    cells = defaultdict(int)
    for key, rs in th["cells"].items():
        t, a = key.split("|", 1)
        cells["{}|{}".format(rename[t], a)] += len(rs)
    row_totals = Counter()
    for t, n in th["row_totals"].items():
        row_totals[rename[t]] += n
    rows = keep + ([OTHER] if OTHER in row_totals else [])

    k = {key: v for key, v in agg["kpis"].items() if key != "files"}
    k["themes"] = len(keep)
    return {
        "generated": agg["generated"],
        "kpis": k,
        "cloud": [{key: v for key, v in term.items() if key != "eg"} for term in agg["cloud"]],
        "themes": {"rows": rows, "cols": th["cols"], "cells": dict(cells),
                   "row_totals": dict(row_totals), "col_totals": th["col_totals"]},
        "methods": agg["methods"],
        "focus": agg["focus"],
        "toolkit": agg["toolkit"],
        "redacted": True,
    }


# --------------------------------------------------------------------------
# dashboard


def dashboard(agg: dict, audience: str, lab: dict, synthetic: bool) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    agg = dict(agg, lab=lab, synthetic=synthetic)
    if synthetic:
        tpl = tpl.replace("<!doctype html>\n", "<!doctype html>\n<!-- SYNTHETIC EXAMPLE: built from "
                          "forage's mock collection. Describes no real lab. -->\n", 1)
    payload = json.dumps(agg, ensure_ascii=False).replace("</", "<\\/")
    return (tpl.replace("__TITLE__", html.escape(lab["name"]))
               .replace("__AUDIENCE__", audience)
               .replace("__DATA__", payload))


def load_lab(args) -> dict:
    """The lab's name, description, PI and recent publications.

    Publications are fetched from PubMed by the agent during the run (workflow
    Step 3) and saved into lab.json, so this script stays offline. They are
    public, so both editions carry them.
    """
    lab = {"name": "Lab", "description": ""}
    if LAB_FILE.exists():
        lab.update(json.loads(LAB_FILE.read_text(encoding="utf-8")))
    if args.lab_name:
        lab["name"] = args.lab_name
    if args.lab_description:
        lab["description"] = args.lab_description
    pi = lab.get("pi") or {}
    return {"name": lab["name"], "description": lab["description"],
            "pi": {"name": pi.get("name", ""), "pubmed_author": pi.get("pubmed_author", "")},
            "publications": lab.get("publications", [])[:5],
            "publications_fetched": lab.get("publications_fetched", "")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--hide-theme", action="append", default=[],
                    help="theme to fold into 'Other' in the collaborator edition; repeatable")
    ap.add_argument("--min-theme-requests", type=int, default=2,
                    help="themes with fewer requests fold into 'Other' for collaborators")
    ap.add_argument("--top", type=int, default=10, help="rows per ranked view")
    ap.add_argument("--lab-name", default="", help="overrides resources/lab.json")
    ap.add_argument("--lab-description", default="", help="overrides resources/lab.json")
    ap.add_argument("--synthetic", action="store_true",
                    help="mark the dashboards as a synthetic example (EXAMPLE_ files only)")
    ap.add_argument("--out-dir", default=str(OUT))
    args = ap.parse_args()

    snap_path = Path(args.snapshot)
    if not snap_path.exists():
        sys.exit("no snapshot at {}\nRun forage first:  cd ../forage && "
                 "./.venv/bin/python scripts/export_snapshot.py".format(snap_path))
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    if snap.get("kind") != "forage_snapshot" or snap.get("schema") != 1:
        sys.exit("{} is not a schema-1 forage snapshot".format(snap_path))

    lab = load_lab(args)
    site = SiteRules(json.loads(LAB_FILE.read_text(encoding="utf-8")) if LAB_FILE.exists() else {})
    fam = Families(json.loads(FAMILIES.read_text(encoding="utf-8")))
    internal = aggregate(snap, fam, args.top, site)
    collab = redact(internal, args.hide_theme, args.min_theme_requests)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = args.date
    files = {
        out / "profile_data_{}.json".format(stem):
            json.dumps(dict(internal, lab=lab), indent=1, ensure_ascii=False),
        out / "profile_data_{}_collab.json".format(stem):
            json.dumps(dict(collab, lab=lab), indent=1, ensure_ascii=False),
        out / "dashboard_{}.html".format(stem): dashboard(internal, "internal", lab, args.synthetic),
        out / "dashboard_{}_collab.html".format(stem): dashboard(collab, "collaborator", lab, args.synthetic),
    }
    for path, text in files.items():
        path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
        print("wrote {} ({:,} bytes)".format(path, path.stat().st_size))
    if not lab["publications"]:
        print("no publications yet: the workflow fetches them from PubMed once the PI's details are in resources/lab.json")
    if not lab["description"]:
        print("no lab description yet: the workflow asks for one on the first run "
              "and saves it to resources/lab.json")
    if internal["ungrouped_themes"]:
        print("themes not in any group (add them to theme_groups in resources/lab.json): " +
              ", ".join(internal["ungrouped_themes"]))
    um = internal["unmatched"]
    if any(um.values()):
        print("unmapped terms (extend resources/families.json if any matter): " +
              "; ".join("{}: {}".format(k, ", ".join(t for t, _ in v[:6])) for k, v in um.items() if v))


if __name__ == "__main__":
    main()
