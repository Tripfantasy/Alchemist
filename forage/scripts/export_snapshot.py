"""Export a read-only, aggregated snapshot of the knowledge store.

The snapshot is forage's public interface to other agents. sigil builds the
lab profile from it and never reads forage's stores directly: forage stays the
only owner of the JSONL formats, and a consumer depends on one documented JSON
shape instead of on kb.py internals.

Everything is aggregated. No per-file records leave forage -- only per-request
and per-"project folder" counts, terms and tier splits.

When the site has a mouse-line registry (resources/mouse_lines.json, built
from the colony list by scripts/mouse_lines.py), it also carries one aggregate
per line: how many folders are named with it, which lines share those folders
(the crosses), and what the line is (class, target, colony status, public).
A line is counted by NAMED folder -- the folder whose own name carries the
genotype -- because one experiment folder holds many files, and per-person
project folders would lump a whole lab member's lines together.

Schema 2 added `mouse_lines`, and narrowed `coverage.archives_unopened` to
archives that can hold a file tree (see minor_archive); the rest are counted
by reason in `coverage.archives_minor`.

It also carries the store's history -- files first catalogued per day, and the
run log -- so a consumer can show how the knowledge base grew.

A project folder (a "unit") is a path truncated to --unit-depth segments. Files
are a poor unit: one ephys session writes hundreds of per-channel files, so
per-file counts measure the instrument, not the work.

Usage
-----
  ./.venv/bin/python scripts/export_snapshot.py                 # -> knowledge/snapshot.json
  ./.venv/bin/python scripts/export_snapshot.py --unit-depth 4 --out other.json
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402
import build_index  # noqa: E402
from mouse_lines import CLASSES, STATUS_LABEL, MouseLines  # noqa: E402

SEP = "!/"
# Archive members are written <archive>.zip!/<member>. Match the whole marker:
# "!/" alone occurs in ordinary folder names.
ZIP_SEP = ".zip" + SEP
DEFAULT_OUT = kb.KB_DIR / "snapshot.json"

# Not every .zip is an archive worth opening. On a lab collection most are one
# file zipped for transfer (a slide-scanner tile, "...Layer0.tif.zip"), an
# ImageJ/ABBA ROI set, or a zarr store (one dataset, indexed as such). Those,
# and anything under --min-archive-mb, are counted separately by reason; only
# the rest -- archives that can hold a real file tree -- count as unopened.
_ZARR = re.compile(r"\.zarr\.zip$", re.I)
_ROI = re.compile(r"roi", re.I)
_WRAPPER = re.compile(
    r"\.(tiff?|csv|txt|xlsx?|czi|oir|nd2|lif|ims|png|jpe?g|pdf|docx?|pptx?|mat|h5|"
    r"fastq|fq|bam|gz|avi|mp4|mov|json|xml)\.zip$|\.vsi\.collection", re.I)


def minor_archive(path: str, size: int, min_bytes: int) -> str:
    """Why a .zip is not a substantial archive, or "" if it is one."""
    name = path.rsplit("/", 1)[-1]
    if _ZARR.search(name):
        return "zarr store"
    if _ROI.search(name):
        return "ROI set"
    if _WRAPPER.search(name):
        return "single-file wrapper"
    if size < min_bytes:
        return "small archive"
    return ""


def unit_of(path: str, depth: int) -> str:
    """The project folder a file belongs to: its first `depth` path segments.

    Archive members are grouped by archive plus their first segment inside
    it (<archive>.zip!/<top>), so a large zip is not one undifferentiated unit.
    """
    outer, marker, inner = path.partition(ZIP_SEP)
    if marker:
        # Directories only: a member at the archive's root belongs to the
        # archive itself, as a loose file belongs to its folder. Otherwise an
        # ROI set of 20k top-level members becomes 20k "project folders".
        top = [s for s in inner.split("/") if s][:-1][:1]
        return outer + ".zip" + (SEP + top[0] if top else "")
    segs = [s for s in outer.split("/") if s]
    return "/" + "/".join(segs[:-1][:depth]) if len(segs) > 1 else "/"


def clean_project(text: str) -> str:
    """'Theme name (CODE-123-XYZ)' -> 'Theme name'."""
    return re.sub(r"\s*\(.*$", "", text or "").strip()


def inventories() -> list:
    out = []
    for p in sorted(kb.KB_DIR.glob("inventory*.jsonl")):
        if ".mock" in p.name:
            continue
        try:
            with p.open(encoding="utf-8") as fh:
                meta = json.loads(fh.readline())
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("kind") != "scan_meta":
            continue
        out.append({
            "file": p.name,
            "source": meta.get("source", "directory_scan"),
            "scanned": meta.get("ts", ""),
            "roots": meta.get("roots", []),
            "depth": meta.get("depth"),
            "excluded": meta.get("exclude", []),
        })
    return out


def exploration_history() -> list:
    """How far the directory scans have reached, scan by scan.

    A folder is *known* once any scan has listed it, and *opened* once any scan
    has listed its contents. Folders at a scan's depth limit are known but not
    opened, so known - opened is the unexplored frontier. Cumulative across
    scans in time order: a deeper scan of one subtree opens folders that the
    broad scan only saw. Archive listings are excluded; archives are counted
    separately in coverage.
    """
    scans = []
    for p in sorted(kb.KB_DIR.glob("inventory*.jsonl")):
        if ".mock" in p.name:
            continue
        with p.open(encoding="utf-8") as fh:
            try:
                meta = json.loads(fh.readline())
            except json.JSONDecodeError:
                continue
        if meta.get("kind") == "scan_meta" and meta.get("source", "directory_scan") == "directory_scan":
            scans.append((meta.get("ts", ""), p))
    known, opened, out = set(), set(), []
    for ts, p in sorted(scans):
        for rec in kb.iter_records(p):
            path = rec.get("path", "")
            if rec.get("kind") not in ("dir", "file") or ZIP_SEP in path:
                continue
            parent = path.rstrip("/").rsplit("/", 1)[0] + "/"
            opened.add(parent)
            known.add(parent)
            if rec["kind"] == "dir":
                known.add(path if path.endswith("/") else path + "/")
        out.append({"date": ts[:10], "known": len(known), "opened": len(opened & known)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit-depth", type=int, default=3,
                    help="path segments that define a project folder (default 3)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--min-archive-mb", type=float, default=10,
                    help="smaller .zip files are not counted as archives to open (default 10)")
    args = ap.parse_args()
    min_bytes = int(args.min_archive_mb * 1e6)

    live = kb.current_state()
    if not live:
        sys.exit("knowledge store is empty -- run scan_endpoint.py then build_index.py")

    by_tier = Counter()
    bytes_by_tier = Counter()
    vocab_versions = Counter()
    units = defaultdict(lambda: {
        "files": 0, "bytes": 0, "by_tier": Counter(),
        "terms": defaultdict(Counter), "ext": Counter(), "requests": Counter(),
    })
    req_files = Counter()
    req_bytes = Counter()
    zips = {}
    listed_archives = set()
    mice = MouseLines.load()
    line_folders = defaultdict(Counter)       # line -> named folder -> files
    folder_lines = defaultdict(set)           # named folder -> lines named in it
    line_units = defaultdict(set)

    for rec in live.values():
        path = rec.get("path", "")
        tier = rec.get("tier", "unknown")
        if tier == "bundled":           # represented by its bundle record instead
            continue
        size = int((rec.get("stat") or {}).get("size") or 0)
        meta = rec.get("metadata") or {}
        by_tier[tier] += 1
        bytes_by_tier[tier] += size
        if rec.get("vocab_version"):
            vocab_versions[str(rec["vocab_version"])] += 1

        if ZIP_SEP in path:
            listed_archives.add(path.split(ZIP_SEP, 1)[0] + ".zip")
        elif path.lower().endswith(".zip"):
            zips[path] = {"path": path, "size": size,
                          "last_modified": str((rec.get("stat") or {}).get("last_modified", ""))[:10]}

        u = units[unit_of(path, args.unit_depth)]
        u["files"] += 1
        u["bytes"] += size
        u["by_tier"][tier] += 1
        u["ext"][rec.get("ext") or ""] += 1
        for cat, terms in (meta.get("by_category") or {}).items():
            for t in terms:
                u["terms"][cat][t] += 1
        if mice and (meta.get("by_category") or {}).get("mouse_line"):
            segs = [s for s in path.split("/") if s]
            for name, i in mice.locate(path).items():
                # a line in a file's own name counts toward the folder holding it
                folder = "/" + "/".join(segs[: min(i + 1, len(segs) - 1)])
                line_folders[name][folder] += 1
                folder_lines[folder].add(name)
                line_units[name].add(unit_of(path, args.unit_depth))
        rid = meta.get("request_id")
        if tier == "csv" and rid:
            u["requests"][rid] += 1
            req_files[rid] += 1
            req_bytes[rid] += size

    # -- history: when each file first entered the store, and the run log.
    # Read from the append-only log (not current_state), because only the log
    # remembers WHEN a file was first catalogued.
    seen = set()
    first_seen = defaultdict(Counter)
    for rec in kb.iter_records(kb.ASSOCIATIONS):
        key = rec.get("file_key")
        if not key or key in seen:
            continue
        seen.add(key)
        first_seen[str(rec.get("ts", ""))[:10]][rec.get("tier", "unknown")] += 1
    runs = []
    for q in kb.iter_records(kb.QUERY_LOG):
        runs.append({
            "date": str(q.get("ts", ""))[:10],
            "goal": str(q.get("goals", ""))[:160],
            "kind": "report" if q.get("report_path") else "quick",
        })

    by_request, _ = build_index.load_requests()
    requests = []
    for rid, m in sorted(by_request.items()):
        requests.append({
            "id": rid,
            "title": m.get("title", ""),
            "project": clean_project(m.get("scientific_project", "")),
            "project_type": m.get("project_type", ""),
            "analysis_goals": m.get("analysis_goals", "")[:400],
            "machine": m.get("machine_type", ""),
            "requester": m.get("requester", ""),
            "status": m.get("status", ""),
            "files_on_endpoint": req_files.get(rid, 0),
            "bytes_on_endpoint": req_bytes.get(rid, 0),
        })

    unit_list = []
    for path, u in units.items():
        unit_list.append({
            "path": path,
            "files": u["files"],
            "bytes": u["bytes"],
            "by_tier": dict(u["by_tier"]),
            "terms": {c: dict(t) for c, t in u["terms"].items()},
            "ext": dict(u["ext"]),
            "requests": dict(u["requests"]),
        })
    unit_list.sort(key=lambda x: -x["files"])

    lines = {}
    for name, folders in line_folders.items():
        with_ = Counter()
        for f in folders:
            for other in folder_lines[f]:
                if other != name:
                    with_[other] += 1
        reg = mice.lines.get(name, {})
        lines[name] = {
            "folders": len(folders),
            "files": sum(folders.values()),
            "units": len(line_units[name]),
            "with": dict(with_.most_common(8)),
            "eg": [f for f, _ in folders.most_common(3)],
            "class": reg.get("class", "Other lines"),
            "target": reg.get("target", ""),
            "official": reg.get("official", ""),
            "status": reg.get("status", "unknown"),
            "public": bool(reg.get("public")),
        }

    unopened, minor = [], Counter()
    for p, z in zips.items():
        if p in listed_archives:
            continue
        why = minor_archive(p, z["size"], min_bytes)
        if why:
            minor[why] += 1
        else:
            unopened.append(z)
    unopened.sort(key=lambda z: -z["size"])

    snapshot = {
        "kind": "forage_snapshot",
        "schema": 2,
        "generated": kb.utc_now(),
        "unit_depth": args.unit_depth,
        "vocab_versions": dict(vocab_versions),
        "store": {"files": sum(by_tier.values()), "by_tier": dict(by_tier),
                  "bytes_by_tier": dict(bytes_by_tier)},
        "coverage": {
            "inventories": inventories(),
            "archives_listed": sorted(listed_archives),
            "archives_unopened": unopened,
            "archives_minor": dict(minor),
            "archive_rule": {"min_mb": args.min_archive_mb,
                             "not_counted": ["single-file wrapper", "ROI set", "zarr store",
                                             "small archive"]},
        },
        "history": {
            "first_seen": {d: dict(c) for d, c in sorted(first_seen.items()) if d},
            "runs": runs,
            "exploration": exploration_history(),
        },
        "requests": requests,
        "units": unit_list,
        "mouse_lines": {
            "registry_version": mice.version if mice else "",
            "registered": len(mice.lines) if mice else 0,
            "classes": CLASSES,
            "status_labels": STATUS_LABEL,
            "lines": lines,
        },
    }
    out = Path(args.out)
    out.write_text(json.dumps(snapshot, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("snapshot -> {} | {:,} files, {} requests, {:,} project folders (depth {}), "
          "{} mouse lines named".format(out, sum(by_tier.values()), len(requests),
                                        len(unit_list), args.unit_depth, len(lines)))


if __name__ == "__main__":
    main()
