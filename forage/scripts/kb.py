"""Append-only knowledge store for file->metadata associations.

Three stores under knowledge/, all newline-delimited JSON:

  file_associations.jsonl  every assertion ever made about a file
  query_log.jsonl          one record per discovery run
  corrections.jsonl        human overrides -- gold labels

Design rules, which the future database-organization agent depends on:

  1. APPEND ONLY. A changed association is a new record carrying
     ``supersedes``, never an edit. The history is signal: it shows where
     metadata is unstable.
  2. PATH IS NOT AN IDENTITY. Paths change when data is transferred. Every
     record also stores the request-ID / flowcell anchors extracted from the
     path, so files can be re-matched after a move.
  3. EVERY ASSERTION NAMES ITS SOURCE. A hard request-ID join and a guess off
     a folder name must never be indistinguishable downstream.

The request-ID format is site-specific and configured in resources/site.json
(gitignored), falling back to resources/site.example.json.

ASSOCIATIONS.md is a regenerated human view; it is derived, never authored.
"""

import hashlib
import json
import os
import re
import zlib
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
    # A file folded into a bundle (e.g. one chunk of a zarr store) after it was
    # already recorded on its own. Outranks machine assertions so the fold
    # sticks; a human correction can still restore the file.
    "bundle_fold": 35,
    "csv_join": 30,
    "model_judgment": 20,
    "vocab_inference": 10,
    "none": 0,
}

# "bundled" marks a record superseded by the bundle that now represents it.
# Consumers that count files skip it; the history stays in the log.
TIERS = ("csv", "inferred", "unknown", "bundled")

RESOURCES = ROOT / "resources"


def resource(name: str) -> Path:
    """A site's own copy of a resource if present, else the shipped example.

    Site files (site.json, vocab.json, metadata.csv, project_codes.json) carry
    one institution's identifiers and stay gitignored. Each ships as an
    *.example.* twin so a fresh clone runs.
    """
    real = RESOURCES / name
    if real.exists():
        return real
    stem, _, ext = name.rpartition(".")
    # Two naming styles ship: site.example.json and metadata_example.csv.
    for candidate in ("{}.example.{}", "{}_example.{}"):
        path = RESOURCES / candidate.format(stem, ext)
        if path.exists():
            return path
    return RESOURCES / "{}.example.{}".format(stem, ext)


def _site() -> dict:
    return json.loads(resource("site.json").read_text(encoding="utf-8"))


SITE = _site()
# The sequencing core's request-ID format, e.g. REQ-1234. The regex's first
# group is the numeric part; `format` rebuilds the canonical ID from it.
REQUEST_RE = re.compile(SITE["request_id"]["regex"], re.IGNORECASE)
REQUEST_FMT = SITE["request_id"]["format"]
REQUEST_COLUMN = SITE["request_id"].get("csv_column", "Request #")
PROJECT_CODE_RE = re.compile(SITE.get("project_code_regex", r"(PRJ-\d{6})"))
# Illumina/NovaSeq flowcell IDs: 9-10 alnum, at least one digit, upper-ish.
# Also allow all-digit run IDs (e.g. 2306080007).
FLOWCELL_RE = re.compile(r"\b(?=[A-Z0-9]{9,10}\b)(?=.*\d)[A-Z0-9]{9,10}\b")


ANCHOR_KEYS = ["request"] + list(SITE.get("legacy_anchor_keys", []))


def request_anchors(anchors: dict) -> List[str]:
    """Request IDs from an anchors dict. Also reads any legacy key names a
    site lists in site.json, so stores written under an older key still work."""
    for key in ANCHOR_KEYS:
        if anchors.get(key):
            return anchors[key]
    return []


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
    pre-transfer prefixes do not exist on the Globus collection.
    """
    requests = [REQUEST_FMT.format(m) for m in REQUEST_RE.findall(path)]
    segments = [s for s in path.split("/") if s]
    flowcells = []
    for seg in segments:
        base = seg.split(".")[0]
        if REQUEST_RE.fullmatch(base):
            continue
        for hit in FLOWCELL_RE.findall(base.upper()):
            flowcells.append(hit)
    return {
        "request": sorted(set(requests)),
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


def build_association(
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
    return payload


def append_association(**kwargs) -> dict:
    """Validate, build and append one association record."""
    payload = build_association(**kwargs)
    store = CORRECTIONS if payload["source"] == "human_correction" else ASSOCIATIONS
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


def terms_signature(metadata: Optional[dict]) -> int:
    """Stable fingerprint of what a record says a file is about.

    Tier, source and confidence can all stay put while the terms change -- a
    new vocabulary word, a mouse line -- so change detection compares this too.
    """
    cats = (metadata or {}).get("by_category") or {}
    return zlib.crc32(json.dumps(cats, sort_keys=True).encode("utf-8"))


def current_fingerprints() -> Dict[str, tuple]:
    """Compact fold: file_key -> (tier, source, confidence, record_id, terms_signature).

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
                         rec.get("record_id", ""),
                         terms_signature(rec.get("metadata")))
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

    # Group by request ID so the view reads the way the core organizes work.
    groups: Dict[str, List[dict]] = {}
    for rec in live.values():
        anchors = request_anchors(rec.get("anchors", {})) or ["(unanchored)"]
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
