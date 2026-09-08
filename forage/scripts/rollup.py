"""Regenerate knowledge/ASSOCIATIONS.md as a bounded summary.

Replaces the naive per-file listing, which at this collection's scale (1.45M
files) would emit a ~100 MB markdown table that no one could read and no
editor would open. A summary that fits on a screen is worth more than an
exhaustive dump.

Memory matters here too. Folding the whole append-only log into live records
and holding them would cost gigabytes, so this runs two streaming passes:

  pass 1  file_key -> (source_rank, ts, record_id) of the winning assertion
  pass 2  re-read, aggregate ONLY the winners, keep nothing else

What the summary shows:
  - counts by tier and source
  - every sequencing request matched by CSV join (small, high value)
  - inferred and undocumented files rolled up per top-level tree
  - the largest undocumented directories, which is the organization-debt
    worklist for the database-organization agent

Usage:
  python3 scripts/rollup.py
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

MAX_REQUEST_ROWS = 60
MAX_TREE_ROWS = 25
MAX_DEBT_ROWS = 40
MAX_TERMS = 6


def _tree(path: str) -> str:
    segs = [s for s in path.split("/") if s]
    return segs[0] if segs else "(root)"


def _parent(path: str) -> str:
    stripped = path.rstrip("/")
    return stripped.rsplit("/", 1)[0] + "/" if "/" in stripped else "/"


def _gb(n: int) -> float:
    return n / 1e9


def winners() -> Dict[str, Tuple[int, str, str]]:
    """Pass 1: which assertion currently governs each file."""
    best: Dict[str, Tuple[int, str, str]] = {}
    for store in (kb.ASSOCIATIONS, kb.CORRECTIONS):
        for rec in kb.iter_records(store):
            key = rec.get("file_key")
            if not key:
                continue
            rank = kb.SOURCE_RANK.get(rec.get("source", "none"), 0)
            ts = str(rec.get("ts", ""))
            incumbent = best.get(key)
            if incumbent is None or (rank, ts) >= (incumbent[0], incumbent[1]):
                best[key] = (rank, ts, rec.get("record_id", ""))
    return best


def build() -> Path:
    best = winners()
    wanted = {k: v[2] for k, v in best.items()}

    tiers: Counter = Counter()
    sources: Counter = Counter()
    requests: Dict[str, dict] = {}
    tree_stats: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {"inferred": 0, "unknown": 0, "csv": 0, "bytes": 0,
                 "terms": Counter(), "exts": Counter()})
    debt: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "bytes": 0})
    total_files = 0
    total_bytes = 0

    # pass 2: aggregate winners only, holding no records
    for store in (kb.ASSOCIATIONS, kb.CORRECTIONS):
        for rec in kb.iter_records(store):
            key = rec.get("file_key")
            if not key or rec.get("record_id") != wanted.get(key):
                continue
            tier = rec.get("tier", "unknown")
            size = int(rec.get("stat", {}).get("size", 0) or 0)
            meta = rec.get("metadata", {})
            path = rec.get("path", "")

            total_files += 1
            total_bytes += size
            tiers[tier] += 1
            sources[rec.get("source", "none")] += 1

            t = tree_stats[_tree(path)]
            t[tier] = t.get(tier, 0) + 1
            t["bytes"] = int(t["bytes"]) + size
            if rec.get("ext"):
                t["exts"][rec["ext"]] += 1

            if tier == "csv":
                rid = rec.get("evidence", {}).get("request_id", "")
                if rid:
                    r = requests.setdefault(rid, {
                        "files": 0, "bytes": 0,
                        "project_type": meta.get("project_type", ""),
                        "project": meta.get("scientific_project", ""),
                        "requester": meta.get("requester", ""),
                        "status": meta.get("status", ""),
                        "paths": set()})
                    r["files"] += 1
                    r["bytes"] += size
                    if len(r["paths"]) < 3:
                        r["paths"].add(_parent(path))
            elif tier == "inferred":
                for term in meta.get("terms", [])[:4]:
                    t["terms"][term] += 1
            else:
                d = debt[_parent(path)]
                d["files"] += 1
                d["bytes"] += size

    L = [
        "# File Associations",
        "",
        "_Generated {} by scripts/rollup.py — derived, do not edit._".format(kb.utc_now()),
        "_Source of truth is the append-only JSONL in `knowledge/`._",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "| --- | --- |",
        "| files tracked | {:,} |".format(total_files),
        "| total size | {:,.1f} TB |".format(total_bytes / 1e12),
        "| attributed to a sequencing request (`csv`) | {:,} |".format(tiers["csv"]),
        "| inferred from path (`inferred`) | {:,} |".format(tiers["inferred"]),
        "| **undocumented (`unknown`)** | **{:,}** |".format(tiers["unknown"]),
        "| distinct requests matched | {:,} |".format(len(requests)),
        "",
        "Sources: "
        + ", ".join("{} {}".format(v, k) for k, v in sources.most_common()),
        "",
    ]

    if tiers["unknown"] and total_files:
        pct = 100.0 * tiers["unknown"] / total_files
        L += ["> **{:.0f}% of files carry no attributable metadata.** That figure is "
              "the organization-debt baseline; §3 lists where it concentrates.".format(pct),
              ""]

    L += ["## 1. Attributed to sequencing requests", "",
          "| request | project type | scientific project | files | size | location |",
          "| --- | --- | --- | --- | --- | --- |"]
    for rid in sorted(requests, key=lambda r: -requests[r]["files"])[:MAX_REQUEST_ROWS]:
        r = requests[rid]
        loc = sorted(r["paths"])[0] if r["paths"] else "-"
        L.append("| `{}` | {} | {} | {:,} | {:.1f} GB | `{}` |".format(
            rid, r["project_type"][:34] or "-", r["project"][:34] or "-",
            r["files"], _gb(r["bytes"]), loc[:58]))
    L.append("")

    L += ["## 2. Inferred from path, by tree", "",
          "| tree | inferred | unknown | size | leading terms |",
          "| --- | --- | --- | --- | --- |"]
    ranked = sorted(tree_stats.items(),
                    key=lambda kv: -(int(kv[1]["inferred"]) + int(kv[1]["unknown"])))
    for name, st in ranked[:MAX_TREE_ROWS]:
        terms = ", ".join(t for t, _ in st["terms"].most_common(MAX_TERMS)) or "-"
        L.append("| `{}` | {:,} | {:,} | {:.1f} GB | {} |".format(
            name[:26], int(st["inferred"]), int(st["unknown"]),
            _gb(int(st["bytes"])), terms[:76]))
    L.append("")

    L += ["## 3. Undocumented — largest directories", "",
          "The organization-debt worklist. Nothing here can be described to a "
          "researcher; a README or naming convention in these directories would "
          "move the most files out of `unknown` per unit of effort.",
          "",
          "| directory | files | size |",
          "| --- | --- | --- |"]
    for path, d in sorted(debt.items(), key=lambda kv: -kv[1]["files"])[:MAX_DEBT_ROWS]:
        L.append("| `{}` | {:,} | {:.1f} GB |".format(
            path[:78], d["files"], _gb(d["bytes"])))
    L.append("")

    kb.KB_DIR.mkdir(parents=True, exist_ok=True)
    kb.ROLLUP.write_text("\n".join(L), encoding="utf-8")
    return kb.ROLLUP


if __name__ == "__main__":
    out = build()
    print("rollup -> {} ({:.0f} KB)".format(out, out.stat().st_size / 1024))
