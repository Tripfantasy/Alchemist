"""Join the endpoint inventory to metadata.csv and write associations.

Three-tier attribution, and every file lands in exactly one tier:

  csv       a MOLNG or flowcell token in the file's path matched a request in
            metadata.csv -> full request metadata, confidence 0.95
  inferred  no match; meaning derived from path tokens via resources/vocab.json
            -> confidence 0.25-0.75, capped below any csv join
  unknown   nothing specific enough to claim. Recorded, but excluded from
            reports. For a database-organization agent these are the payload:
            they are precisely the files nobody has documented.

Why token matching and not path matching: the CSV's Flowcell Result Paths are
pre-transfer (/n/analysis/<lab>/...) and do not exist on the Globus collection.
MOLNG ids and flowcell ids survive the move; path prefixes do not.

Usage
-----
  python3 scripts/build_index.py                        # uses knowledge/inventory.jsonl
  python3 scripts/build_index.py --inventory path.jsonl --dry-run
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _metadata_csv() -> Path:
    """Real metadata if present, else the synthetic example.

    metadata.csv carries named requesters and internal paths, so it is
    gitignored and never ships. A fresh clone gets metadata_example.csv -- same
    35 columns, synthetic rows -- so the mock pipeline runs out of the box.
    """
    real = ROOT / "resources" / "metadata.csv"
    return real if real.exists() else ROOT / "resources" / "metadata_example.csv"


METADATA_CSV = _metadata_csv()
VOCAB_JSON = ROOT / "resources" / "vocab.json"
PROJECT_CODES_JSON = ROOT / "resources" / "project_codes.json"
INVENTORY = ROOT / "knowledge" / "inventory.jsonl"
COVERAGE = ROOT / "knowledge" / "coverage.json"

CSV_CONFIDENCE = 0.95
# Categories that carry real biological meaning. A hit in one of these can
# stand alone; a bare modifier like "ctrl" cannot.
SPECIFIC = ("tissue", "assay", "gene", "condition")
WEAK = ("modifier", "species", "stage")


# --------------------------------------------------------------------------
# metadata csv


def load_requests() -> Tuple[Dict[str, dict], Dict[str, str]]:
    """Return (molng -> request metadata, flowcell -> molng)."""
    if not METADATA_CSV.exists():
        sys.exit("missing {}".format(METADATA_CSV))

    by_molng: Dict[str, dict] = {}
    flowcell_to_molng: Dict[str, str] = {}

    with METADATA_CSV.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            rid = (row.get("Request #") or "").strip().upper()
            if not rid:
                continue
            meta = {
                "request_id": rid,
                "title": _clean(row.get("Request Title")),
                "requester": _clean(row.get("Requester")),
                "lab": _clean(row.get("Department/Lab")),
                "project_type": _clean(row.get("Project Type")),
                "scientific_project": _clean(row.get("Scientific Projects")),
                "analysis_goals": _clean(row.get("Analysis Goals"), limit=1200),
                "machine_type": _clean(row.get("Machine Type")),
                "read_type": _clean(row.get("Read Type")),
                "read_length": _clean(row.get("Read Length")),
                "status": _clean(row.get("Status")),
                "requested_date": _clean(row.get("Requested Date")),
                "completed_date": _clean(row.get("Completed Date")),
                "special_instructions": _clean(row.get("Special Instructions"), limit=600),
                "pooling_comments": _clean(row.get("Pooling Comments"), limit=600),
                "csv_flowcell_paths": _clean(row.get("Flowcell Result Paths"), limit=800),
                "csv_analysis_paths": _clean(row.get("Analysis Result Paths"), limit=800),
            }
            meta["project_code"] = _project_code(meta["scientific_project"])
            by_molng[rid] = meta

            for anchor in kb.extract_anchors(meta["csv_flowcell_paths"])["flowcell"]:
                flowcell_to_molng[anchor] = rid

    return by_molng, flowcell_to_molng


def _clean(value: Optional[str], limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    return text[:limit]


def _project_code(text: str) -> str:
    m = re.search(r"(SCI-\d{6})", text or "")
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# vocabulary inference


class Vocab:
    def __init__(self, data: dict):
        self.version = str(data.get("version", "0"))
        self.ambiguous: Set[str] = {a.lower() for a in data.get("ambiguous", [])}
        self.categories: Dict[str, Dict[str, str]] = {}
        for cat in SPECIFIC + WEAK:
            self.categories[cat] = {
                k.lower(): v for k, v in (data.get(cat) or {}).items()
            }
        self.ext_roles: Dict[str, dict] = data.get("extension_roles", {})
        self.bundles: dict = data.get("instrument_bundles", {})
        nd = data.get("non_data_extensions", {})
        self.nondata_ext: Set[str] = {e.lower() for e in nd.get("extensions", [])}
        self.nondata_names: Set[str] = {n.lower() for n in nd.get("filenames", [])}
        self.nondata_prefixes = tuple(p.lower() for p in nd.get("filename_prefixes", []))
        self.project_codes: Dict[str, str] = data.get("project_codes", {})

    @classmethod
    def load(cls) -> "Vocab":
        data = json.loads(VOCAB_JSON.read_text(encoding="utf-8"))
        # Project codes are site-specific -- they name real internal projects,
        # so they live in a gitignored side file rather than in the shared
        # vocabulary. Absent, code-based labelling is simply skipped.
        side = PROJECT_CODES_JSON
        if side.exists():
            codes = json.loads(side.read_text(encoding="utf-8"))
            data["project_codes"] = {
                k: v for k, v in codes.items() if not k.startswith("_")
            }
        return cls(data)

    def tokenize(self, path: str) -> List[str]:
        """Split a path into candidate vocabulary tokens.

        Handles snake_case, kebab-case, dots, and camelCase run-ons, so
        /sc_OE_h19/CriticalPeriod/x.rmd yields sc, oe, h19, critical, period.

        Two guards against spurious short matches: the file extension is
        stripped before tokenizing (otherwise "integrated.h5ad" decomposes to
        h/5/ad and "ad" reads as Alzheimer's), and sub-splitting fires only on
        genuine camelCase, never on digit boundaries inside an alnum run.
        """
        segments = [s for s in path.split("/") if s]
        tokens: List[str] = []
        for i, segment in enumerate(segments):
            if i == len(segments) - 1:
                ext = kb._ext(segment)
                if ext:
                    segment = segment[: -len(ext)]
            for piece in re.split(r"[^A-Za-z0-9]+", segment):
                if not piece:
                    continue
                tokens.append(piece.lower())
                if not re.search(r"[a-z][A-Z]", piece):
                    continue  # not camelCase -- don't invent fragments
                for sub in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", piece):
                    if len(sub) >= 3 and sub.lower() != piece.lower():
                        tokens.append(sub.lower())

        # Bigram pass: multi-word concepts get written apart as often as
        # together ("critical_period", "CriticalPeriod"), so also test each
        # adjacent pair joined. Keeps single-word keys working unchanged.
        joined = [tokens[i] + tokens[i + 1] for i in range(len(tokens) - 1)]
        return tokens + joined

    def is_non_data(self, path: str) -> bool:
        """A document/presentation/system file rather than experimental data."""
        name = path.rstrip("/").rsplit("/", 1)[-1].lower()
        if name in self.nondata_names or name.startswith(self.nondata_prefixes):
            return True
        return kb._ext(name) in self.nondata_ext

    def interpret(self, path: str) -> dict:
        """Map a path to biological meaning. Refuses vague tokens."""
        hits: Dict[str, Dict[str, str]] = defaultdict(dict)
        overloaded: List[str] = []

        leaf = path.rstrip("/").rsplit("/", 1)[-1]
        leaf_tokens = set(self.tokenize(leaf))
        from_leaf = False

        for token in self.tokenize(path):
            if token in self.ambiguous or len(token) < 2:
                continue
            matched_cats = [
                cat for cat, table in self.categories.items() if token in table
            ]
            if not matched_cats:
                continue
            if len(matched_cats) > 1:
                # e.g. "tg" is both trigeminal ganglion and transgenic. Keep
                # both readings and flag it rather than silently picking one.
                overloaded.append(token)
            if token in leaf_tokens:
                from_leaf = True
            for cat in matched_cats:
                hits[cat][token] = self.categories[cat][token]

        specific_cats = [c for c in SPECIFIC if hits.get(c)]
        weak_cats = [c for c in WEAK if hits.get(c)]

        # "If all of these are too vague, do not consider."
        qualifies = bool(specific_cats) or len(weak_cats) >= 2

        # A slide deck, thesis chapter or Thumbs.db is ABOUT the biology,
        # never an instance of it -- "Labmeeting_Xenium.pptx" is a talk, not
        # Xenium data, so naming the topic in the filename must not rescue it.
        if qualifies and self.is_non_data(path):
            qualifies = False

        confidence = 0.0
        if qualifies:
            confidence = 0.25 + 0.15 * len(specific_cats) + 0.05 * len(weak_cats)
            if overloaded:
                confidence -= 0.05
            confidence = max(0.25, min(0.75, confidence))

        terms: List[str] = []
        for cat in SPECIFIC + WEAK:
            terms.extend(sorted(set(hits.get(cat, {}).values())))

        return {
            "non_data": self.is_non_data(path),
            "from_leaf": from_leaf,
            "qualifies": qualifies,
            "confidence": confidence,
            "terms": terms,
            "by_category": {c: sorted(set(v.values())) for c, v in hits.items()},
            "overloaded_tokens": sorted(set(overloaded)),
        }

    def describe_ext(self, ext: str) -> dict:
        return self.ext_roles.get(ext, {"role": "unrecognised type", "group": "other"})


# --------------------------------------------------------------------------
# indexing


def read_inventory(path: Path) -> Tuple[dict, List[dict]]:
    if not path.exists():
        sys.exit(
            "missing inventory {}\nRun scripts/scan_endpoint.py first.".format(path)
        )
    meta: dict = {}
    files: List[dict] = []
    errors: List[dict] = []
    for rec in kb.iter_records(path):
        kind = rec.get("kind")
        if kind == "scan_meta":
            meta = rec
        elif kind == "file":
            files.append(rec)
        elif kind == "error":
            errors.append(rec)
    meta["_errors"] = errors
    return meta, files


def collapse_instrument_bundles(
    files: List[dict], vocab: Vocab
) -> Tuple[List[dict], dict]:
    """Fold per-channel instrument output into one record per session.

    Neuralynx writes one .ncs/.nse per channel, Olympus one .oir per frame, so
    a single recording becomes 30-500 near-identical files. Left alone they
    dominate the store and make any report touching them unreadable.

    A directory holding at least `threshold` files of a bundling extension
    becomes ONE record for the directory, carrying the count and total size.
    Files below threshold pass through untouched -- three .tif files are
    figures, not a session.
    """
    cfg = vocab.bundles
    thresholds = cfg.get("thresholds", {})
    labels = cfg.get("labels", {})
    if not thresholds:
        return files, {"bundles": 0, "files_folded": 0}

    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    passthrough: List[dict] = []
    for entry in files:
        ext = entry.get("ext", "")
        if ext in thresholds:
            parent = entry["path"].rsplit("/", 1)[0] + "/"
            groups[(parent, ext)].append(entry)
        else:
            passthrough.append(entry)

    folded = 0
    made = 0
    for (parent, ext), members in groups.items():
        if len(members) < thresholds[ext]:
            passthrough.extend(members)
            continue
        folded += len(members)
        made += 1
        total = sum(m.get("size", 0) for m in members)
        newest = max((m.get("last_modified", "") for m in members), default="")
        passthrough.append({
            "kind": "bundle",
            "path": parent,
            "name": parent.rstrip("/").rsplit("/", 1)[-1],
            "ext": ext,
            "size": total,
            "last_modified": newest,
            "depth": members[0].get("depth", 0),
            "anchors": kb.extract_anchors(parent),
            "bundle": True,
            "bundle_count": len(members),
            "bundle_label": labels.get(ext, "instrument session"),
        })

    passthrough.sort(key=lambda e: e["path"])
    return passthrough, {"bundles_created": made,
                         "files_folded": folded,
                         "records_before": len(files),
                         "records_after": len(passthrough)}


def classify(
    entry: dict,
    by_molng: Dict[str, dict],
    flowcell_to_molng: Dict[str, str],
    vocab: Vocab,
) -> dict:
    """Assign one file to a tier with metadata, source, and evidence."""
    anchors = entry.get("anchors") or kb.extract_anchors(entry["path"])
    ext_info = dict(vocab.describe_ext(entry.get("ext", "")))
    if entry.get("bundle"):
        ext_info["role"] = "{} ({} files)".format(
            entry.get("bundle_label", "instrument session"),
            entry.get("bundle_count", 0))

    # tier 1: hard join on MOLNG, else on flowcell id
    matched_id = next((m for m in anchors.get("molng", []) if m in by_molng), None)
    via = "molng"
    if not matched_id:
        for fc in anchors.get("flowcell", []):
            if fc in flowcell_to_molng:
                matched_id = flowcell_to_molng[fc]
                via = "flowcell:" + fc
                break

    if matched_id:
        meta = dict(by_molng[matched_id])
        meta["file_role"] = ext_info["role"]
        meta["file_group"] = ext_info["group"]
        meta["terms"] = _terms_from_request(meta)
        if entry.get("bundle"):
            meta["bundle_count"] = entry["bundle_count"]
        return {
            "tier": "csv",
            "source": "csv_join",
            "confidence": CSV_CONFIDENCE,
            "metadata": meta,
            "evidence": {"matched_via": via, "request_id": matched_id,
                         "anchors": anchors},
        }

    # tier 2: vocabulary inference over the path
    reading = vocab.interpret(entry["path"])
    if reading["qualifies"]:
        return {
            "tier": "inferred",
            "source": "vocab_inference",
            "confidence": reading["confidence"],
            "metadata": {
                "terms": reading["terms"],
                "by_category": reading["by_category"],
                "file_role": ext_info["role"],
                "file_group": ext_info["group"],
                "bundle_count": entry.get("bundle_count", 0),
            },
            "evidence": {
                "matched_via": "path_tokens",
                "term_in_filename": reading["from_leaf"],
                "non_data_file": reading["non_data"],
                "overloaded_tokens": reading["overloaded_tokens"],
                "anchors": anchors,
            },
        }

    # tier 3: not enough to claim anything
    return {
        "tier": "unknown",
        "source": "vocab_inference",
        "confidence": 0.0,
        "metadata": {"file_role": ext_info["role"], "file_group": ext_info["group"],
                     "terms": [], "bundle_count": entry.get("bundle_count", 0)},
        "evidence": {"matched_via": "none", "anchors": anchors,
                     "note": "no MOLNG/flowcell match and path tokens too vague"},
    }


def _terms_from_request(meta: dict) -> List[str]:
    terms = []
    for field in ("project_type", "scientific_project", "machine_type"):
        if meta.get(field):
            terms.append(meta[field])
    return terms


def build_coverage(
    files: List[dict],
    classified: List[dict],
    by_molng: Dict[str, dict],
    scan_meta: dict,
) -> dict:
    """Everything the gap section of the report needs."""
    seen_requests: Set[str] = set()
    tier_counts: Dict[str, int] = defaultdict(int)
    group_counts: Dict[str, int] = defaultdict(int)
    bytes_by_tier: Dict[str, int] = defaultdict(int)

    for entry, verdict in zip(files, classified):
        tier_counts[verdict["tier"]] += 1
        bytes_by_tier[verdict["tier"]] += entry.get("size", 0)
        group_counts[verdict["metadata"].get("file_group", "other")] += 1
        rid = verdict.get("evidence", {}).get("request_id")
        if rid:
            seen_requests.add(rid)

    missing = sorted(set(by_molng) - seen_requests)
    # Requests the CSV itself never gave a path for -- distinct from requests
    # that had a path but whose files are absent from the scanned scope.
    never_pathed = sorted(
        r for r in missing if not by_molng[r].get("csv_flowcell_paths")
    )
    pathed_but_absent = sorted(set(missing) - set(never_pathed))

    return {
        "generated": kb.utc_now(),
        "collection_id": scan_meta.get("collection_id", ""),
        "collection_name": scan_meta.get("collection_name", ""),
        "roots_scanned": scan_meta.get("roots", []),
        "type_filter": scan_meta.get("types", []),
        "files_scanned": len(files),
        "files_by_tier": dict(tier_counts),
        "bytes_by_tier": dict(bytes_by_tier),
        "files_by_group": dict(group_counts),
        "requests_total": len(by_molng),
        "requests_with_files": len(seen_requests),
        "requests_matched": sorted(seen_requests),
        "requests_missing_no_path_in_csv": never_pathed,
        "requests_missing_path_but_absent": pathed_but_absent,
        "unreadable_paths": [e["path"] for e in scan_meta.get("_errors", [])],
        "note_analysis_paths_empty": (
            "Analysis Result Paths is 0%% populated across all %d requests, so no "
            "derived analysis output can be attributed by CSV join; such files can "
            "only reach the 'inferred' tier." % len(by_molng)
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inventory", default=str(INVENTORY))
    ap.add_argument("--dry-run", action="store_true",
                    help="classify and summarise without writing to the knowledge store")
    ap.add_argument("--run-id", default="")
    args = ap.parse_args()

    scan_meta, files = read_inventory(Path(args.inventory))
    by_molng, flowcell_to_molng = load_requests()
    vocab = Vocab.load()
    run_id = args.run_id or kb.new_run_id()
    collection = scan_meta.get("collection_id", "unknown")

    print("requests: {} | flowcell keys: {} | vocab v{}".format(
        len(by_molng), len(flowcell_to_molng), vocab.version))
    print("inventory: {} files from {}".format(len(files), args.inventory))

    files, fold = collapse_instrument_bundles(files, vocab)
    if fold["bundles_created"]:
        print("bundled: {} instrument sessions absorbed {} per-channel files "
              "({} -> {} records)".format(
                  fold["bundles_created"], fold["files_folded"],
                  fold["records_before"], fold["records_after"]))

    verdicts = [classify(f, by_molng, flowcell_to_molng, vocab) for f in files]

    if not args.dry_run:
        live = kb.current_fingerprints()
        written = 0
        for entry, verdict in zip(files, verdicts):
            key = kb.file_key(collection, entry["path"])
            prior = live.get(key)
            # Skip a rewrite when nothing changed, so the log records real
            # transitions instead of one duplicate per scan.
            if prior and prior[0] == verdict["tier"] and prior[1] == verdict["source"] \
                    and abs(prior[2] - verdict["confidence"]) < 1e-6:
                continue
            kb.append_association(
                collection_id=collection,
                path=entry["path"],
                tier=verdict["tier"],
                source=verdict["source"],
                metadata=verdict["metadata"],
                confidence=verdict["confidence"],
                evidence=verdict["evidence"],
                stat={"size": entry.get("size", 0),
                      "last_modified": entry.get("last_modified", "")},
                run_id=run_id,
                vocab_version=vocab.version,
                supersedes=prior[3] if prior else None,
            )
            written += 1
        print("associations written: {} (unchanged skipped)".format(written))
        import rollup
        rollup.build()
        print("rollup -> {}".format(kb.ROLLUP))

    coverage = build_coverage(files, verdicts, by_molng, scan_meta)
    if not args.dry_run:
        COVERAGE.parent.mkdir(parents=True, exist_ok=True)
        COVERAGE.write_text(json.dumps(coverage, indent=2), encoding="utf-8")
        print("coverage -> {}".format(COVERAGE))

    print("\ntiers: {}".format(coverage["files_by_tier"]))
    print("requests with files on endpoint: {}/{}".format(
        coverage["requests_with_files"], coverage["requests_total"]))


if __name__ == "__main__":
    main()
