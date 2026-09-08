"""Append-only knowledge store for file->metadata associations.

Three stores under knowledge/, all newline-delimited JSON:

  file_associations.jsonl  every assertion ever made about a file
  query_log.jsonl          one record per discovery run
  corrections.jsonl        human overrides -- gold labels

Design rules, which the future database-organization agent depends on:

  1. APPEND ONLY. A changed association is a new record carrying
     ``supersedes``, never an edit. The history is signal: it shows where
     metadata is unstable.
  2. PATH IS NOT AN IDENTITY. Paths already changed once when this data was
     transferred to Globus. Every record also stores the MOLNG / flowcell
     anchors extracted from the path, so files can be re-matched after a move.
  3. EVERY ASSERTION NAMES ITS SOURCE. A hard MOLNG join and a guess off a
     folder name must never be indistinguishable downstream.

ASSOCIATIONS.md is a regenerated human view; it is derived, never authored.
"""

import hashlib
import json
import os
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge"

ASSOCIATIONS = KB_DIR / "file_associations.jsonl"
QUERY_LOG = KB_DIR / "query_log.jsonl"
CORRECTIONS = KB_DIR / "corrections.jsonl"
ROLLUP = KB_DIR / "ASSOCIATIONS.md"

# Higher wins when folding the log down to current state. A human correction
# always beats a machine assertion regardless of recency.
SOURCE_RANK = {
    "human_correction": 40,
    "csv_join": 30,
    "model_judgment": 20,
    "vocab_inference": 10,
    "none": 0,
}

TIERS = ("csv", "inferred", "unknown")

MOLNG_RE = re.compile(r"MOLNG[-_]?(\d{3,5})", re.IGNORECASE)
# Illumina/NovaSeq flowcell IDs: 9-10 alnum, at least one digit, upper-ish.
# Also allow the all-digit run IDs seen in the CSV (e.g. 2306080007).
FLOWCELL_RE = re.compile(r"\b(?=[A-Z0-9]{9,10}\b)(?=.*\d)[A-Z0-9]{9,10}\b")


def utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    return "run-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def file_key(collection_id: str, path: str) -> str:
    """Stable-ish identity for a file at a point in time."""
    return hashlib.sha1(
        "{}|{}".format(collection_id, path).encode("utf-8")
    ).hexdigest()[:16]


def record_id(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def extract_anchors(path: str) -> Dict[str, List[str]]:
    """Pull prefix-independent join keys out of a path.

    These survive re-rooting, which full paths do not -- the CSV's
    /n/analysis/... prefixes do not exist on the Globus collection.
    """
    molng = ["MOLNG-{}".format(m) for m in MOLNG_RE.findall(path)]
    segments = [s for s in path.split("/") if s]
    flowcells = []
    for seg in segments:
        base = seg.split(".")[0]
        if MOLNG_RE.fullmatch(base):
            continue
        for hit in FLOWCELL_RE.findall(base.upper()):
            flowcells.append(hit)
    return {
        "molng": sorted(set(molng)),
        "flowcell": sorted(set(flowcells)),
    }


# --------------------------------------------------------------------------
# writing


def _append(store: Path, record: dict) -> dict:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return record


class BulkAppender:
    """Hold the store open across a bulk build.

    _append() reopens the file per record, which is right for a one-off
    correction but costs a million open/close cycles on a full rebuild. Use
    this as a context manager when writing many records at once:

        with kb.BulkAppender() as bulk:
            for ...:
                bulk.add(kb.build_association(...))
    """

    def __init__(self, store: Optional[Path] = None):
        self.store = store or ASSOCIATIONS
        self._fh = None
        self.count = 0

    def __enter__(self) -> "BulkAppender":
        KB_DIR.mkdir(parents=True, exist_ok=True)
        self._fh = self.store.open("a", encoding="utf-8")
        return self

    def add(self, record: dict) -> dict:
        self._fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        self.count += 1
        return record

    def __exit__(self, *exc) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


def append_association(
    collection_id: str,
    path: str,
    tier: str,
    source: str,
    metadata: Optional[dict] = None,
    confidence: float = 0.0,
    evidence: Optional[dict] = None,
    stat: Optional[dict] = None,
    run_id: str = "",
    vocab_version: str = "",
    supersedes: Optional[str] = None,
) -> dict:
    if tier not in TIERS:
        raise ValueError("tier must be one of {}: got {!r}".format(TIERS, tier))
    if source not in SOURCE_RANK:
        raise ValueError("unknown source {!r}".format(source))

    name = path.rstrip("/").split("/")[-1]
    payload = {
        "type": "file_association",
        "ts": utc_now(),
        "run_id": run_id,
        "collection_id": collection_id,
        "path": path,
        "name": name,
        "ext": _ext(name),
        "file_key": file_key(collection_id, path),
        "anchors": extract_anchors(path),
        "tier": tier,
        "source": source,
        "confidence": round(float(confidence), 3),
        "metadata": metadata or {},
        "evidence": evidence or {},
        "stat": stat or {},
        "vocab_version": vocab_version,
        "supersedes": supersedes,
    }
    payload["record_id"] = record_id(payload)
    store = CORRECTIONS if source == "human_correction" else ASSOCIATIONS
    return _append(store, payload)


def append_query(
    run_id: str,
    goals: str,
    filters: dict,
    results: List[dict],
    gaps: Optional[dict] = None,
    report_path: str = "",
) -> dict:
    payload = {
        "type": "query",
        "ts": utc_now(),
        "run_id": run_id,
        "goals": goals,
        "filters": filters,
        "result_count": len(results),
        "results": results,
        "gaps": gaps or {},
        "report_path": report_path,
    }
    payload["record_id"] = record_id(payload)
    return _append(QUERY_LOG, payload)


def _ext(name: str) -> str:
    lowered = name.lower()
    for double in (".fastq.gz", ".fq.gz", ".nii.gz", ".vcf.gz", ".tar.gz", ".bed.gz"):
        if lowered.endswith(double):
            return double
    _, dot, tail = lowered.rpartition(".")
    return dot + tail if dot else ""


# --------------------------------------------------------------------------
# reading


def iter_records(store: Path) -> Iterator[dict]:
    if not store.exists():
        return
    with store.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # A truncated tail line shouldn't destroy the whole store.
                print("kb: skipping malformed line {} in {}".format(line_no, store.name))


def current_state() -> "OrderedDict[str, dict]":
    """Fold the append-only log into one live record per file.

    Corrections are read last and outrank everything, so a human override
    always wins even against a later machine scan.
    """
    live: "OrderedDict[str, dict]" = OrderedDict()
    for store in (ASSOCIATIONS, CORRECTIONS):
        for rec in iter_records(store):
            key = rec.get("file_key")
            if not key:
                continue
            incumbent = live.get(key)
            if incumbent is None or _outranks(rec, incumbent):
                live[key] = rec
    return live


def _outranks(candidate: dict, incumbent: dict) -> bool:
    c_rank = SOURCE_RANK.get(candidate.get("source", "none"), 0)
    i_rank = SOURCE_RANK.get(incumbent.get("source", "none"), 0)
    if c_rank != i_rank:
        return c_rank > i_rank
    return str(candidate.get("ts", "")) >= str(incumbent.get("ts", ""))


def current_fingerprints() -> Dict[str, tuple]:
    """Compact fold: file_key -> (tier, source, confidence, record_id).

    current_state() holds whole records, which costs gigabytes once the store
    passes a million files. Callers that only need to detect a CHANGE want
    this instead -- it keeps a 4-tuple per file, not the record.
    """
    live: Dict[str, tuple] = {}
    ranked: Dict[str, tuple] = {}
    for store in (ASSOCIATIONS, CORRECTIONS):
        for rec in iter_records(store):
            key = rec.get("file_key")
            if not key:
                continue
            order = (SOURCE_RANK.get(rec.get("source", "none"), 0),
                     str(rec.get("ts", "")))
            if key in ranked and order < ranked[key]:
                continue
            ranked[key] = order
            live[key] = (rec.get("tier"), rec.get("source"),
                         float(rec.get("confidence", 0.0)),
                         rec.get("record_id", ""))
    return live


def stats() -> dict:
    live = current_state()
    by_tier: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    for rec in live.values():
        by_tier[rec["tier"]] = by_tier.get(rec["tier"], 0) + 1
        by_source[rec["source"]] = by_source.get(rec["source"], 0) + 1
    return {
        "files": len(live),
        "by_tier": by_tier,
        "by_source": by_source,
        "assertions": sum(1 for _ in iter_records(ASSOCIATIONS)),
        "corrections": sum(1 for _ in iter_records(CORRECTIONS)),
        "queries": sum(1 for _ in iter_records(QUERY_LOG)),
    }


# --------------------------------------------------------------------------
# rollup


def write_rollup() -> Path:
    """Regenerate the human-readable view of current state."""
    live = current_state()
    st = stats()
    lines = [
        "# File Associations",
        "",
        "_Generated {} by scripts/kb.py -- do not edit; edit the JSONL stores._".format(
            utc_now()
        ),
        "",
        "- Files tracked: **{}**".format(st["files"]),
        "- Total assertions: {} | corrections: {} | queries logged: {}".format(
            st["assertions"], st["corrections"], st["queries"]
        ),
        "- By tier: "
        + ", ".join("{} {}".format(v, k) for k, v in sorted(st["by_tier"].items())),
        "",
    ]

    # Group by MOLNG so the view reads the way the core organizes work.
    groups: Dict[str, List[dict]] = {}
    for rec in live.values():
        anchors = rec.get("anchors", {}).get("molng") or ["(unanchored)"]
        groups.setdefault(anchors[0], []).append(rec)

    for anchor in sorted(groups, key=lambda a: (a == "(unanchored)", a)):
        members = sorted(groups[anchor], key=lambda r: r["path"])
        sample = members[0].get("metadata", {})
        heading = anchor
        if sample.get("project_type"):
            heading += " -- {}".format(sample["project_type"])
        lines.append("## {} ({} files)".format(heading, len(members)))
        if sample.get("scientific_project"):
            lines.append("_{}_".format(sample["scientific_project"]))
        lines.append("")
        lines.append("| file | tier | source | conf | terms |")
        lines.append("| --- | --- | --- | --- | --- |")
        for rec in members:
            terms = ", ".join(rec.get("metadata", {}).get("terms", [])) or "-"
            lines.append(
                "| `{}` | {} | {} | {:.2f} | {} |".format(
                    rec["path"], rec["tier"], rec["source"], rec["confidence"], terms
                )
            )
        lines.append("")

    KB_DIR.mkdir(parents=True, exist_ok=True)
    ROLLUP.write_text("\n".join(lines), encoding="utf-8")
    return ROLLUP


if __name__ == "__main__":
    import pprint

    pprint.pprint(stats())
    print("rollup ->", write_rollup())
