"""Query the knowledge store for files relevant to a research goal.

This does the mechanical half of relevance -- token overlap, synonym
expansion, filtering -- and emits ranked candidates as JSON. The agent then
does the semantic half: judging whether a candidate genuinely serves the
stated goal, and writing the report.

Deliberately lexical. It is a recall device, not a judge; it casts wide and
lets the agent cut. Anything in the 'unknown' tier is excluded by default
(--include-unknown to see it) because unattributed files cannot be honestly
described to a researcher -- but they are still counted, and they feed the
gap analysis.

Usage
-----
  python3 scripts/search.py "APOE4 organoid gene regulatory networks" \
      --types omics,tabular --folder /projects/yu/ --limit 40
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402
from build_index import Vocab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "knowledge" / "coverage.json"

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
    "has", "have", "had", "our", "their", "its", "into", "over", "under",
    "about", "any", "all", "can", "could", "would", "should", "want", "need",
    "looking", "interested", "data", "dataset", "datasets", "study", "studies",
    "analysis", "analyses", "project", "research", "goal", "goals", "using",
    "use", "used", "how", "what", "which", "where", "who", "why", "does",
}

# Weights reflect how much a field says about what a file actually contains.
FIELD_WEIGHTS = {
    "analysis_goals": 3.0,
    "scientific_project": 2.5,
    "project_type": 2.5,
    "terms": 2.0,
    "title": 2.0,
    "machine_type": 1.0,
    "special_instructions": 0.8,
    "pooling_comments": 0.5,
    "path": 1.5,
    "file_role": 0.8,
}


def query_tokens(text: str, vocab: Vocab) -> Set[str]:
    """Tokenize the goal and expand it with vocabulary synonyms.

    A goal that says "olfactory epithelium" should also match a path that only
    says "OE", so expansion runs in both directions.
    """
    words = {
        w for w in re.findall(r"[a-z0-9][a-z0-9\-]{1,}", text.lower())
        if w not in STOPWORDS
    }
    expanded = set(words)
    for table in vocab.categories.values():
        for abbrev, meaning in table.items():
            meaning_words = set(re.findall(r"[a-z0-9]{2,}", meaning.lower()))
            if abbrev in words:
                expanded |= meaning_words
            if meaning_words and meaning_words <= words:
                expanded.add(abbrev)
            elif len(meaning_words & words) >= 2:
                # Require two shared words, not one. Otherwise "gene" in a goal
                # pulls in "ieg" (immediate early gene) and every other multi-
                # word term that merely contains it.
                expanded.add(abbrev)
    return {w for w in expanded if w not in STOPWORDS}


def field_text(record: dict, field: str) -> str:
    if field == "path":
        return record.get("path", "")
    value = record.get("metadata", {}).get(field, "")
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def score(record: dict, terms: Set[str]) -> Dict[str, object]:
    total = 0.0
    matched: Dict[str, List[str]] = {}
    for field, weight in FIELD_WEIGHTS.items():
        text = field_text(record, field).lower()
        if not text:
            continue
        hits = sorted({t for t in terms if t in text})
        if hits:
            # sublinear in hit count so one verbose field can't dominate
            total += weight * (1 + 0.5 * (len(hits) - 1))
            matched[field] = hits
    # a low-confidence inference should not outrank a hard CSV join
    total *= 0.5 + 0.5 * float(record.get("confidence", 0.0))
    return {"score": round(total, 3), "matched": matched}


def passes_filters(
    record: dict,
    exts: Optional[Set[str]],
    folders: List[str],
    tiers: Set[str],
) -> bool:
    if record.get("tier") not in tiers:
        return False
    if exts and record.get("ext") not in exts:
        return False
    if folders:
        path = record.get("path", "")
        if not any(path.startswith(f) for f in folders):
            return False
    return True


def load_type_filter(spec: str, vocab_raw: dict) -> Optional[Set[str]]:
    if not spec.strip():
        return None
    groups = vocab_raw["type_groups"]
    exts: Set[str] = set()
    for name in (n.strip().lower() for n in spec.split(",") if n.strip()):
        if name in groups:
            exts.update(groups[name])
        elif name.startswith("."):
            exts.add(name)
        else:
            sys.exit("unknown type group {!r}; choose from {}".format(
                name, ", ".join(sorted(groups))))
    return exts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("goal", help="research goal / project description")
    ap.add_argument("--types", default="", help="type groups or .exts")
    ap.add_argument("--folder", action="append", default=[],
                    help="restrict to paths under this prefix; repeatable")
    ap.add_argument("--limit", type=int, default=40, help="max candidates")
    ap.add_argument("--per-request", type=int, default=5,
                    help="max files shown per MOLNG request, so one large "
                         "request cannot crowd out the rest")
    ap.add_argument("--min-score", type=float, default=0.5)
    ap.add_argument("--include-unknown", action="store_true")
    ap.add_argument("--out", default="", help="write JSON here instead of stdout")
    args = ap.parse_args()

    vocab_raw = json.loads((ROOT / "resources" / "vocab.json").read_text())
    vocab = Vocab(vocab_raw)
    exts = load_type_filter(args.types, vocab_raw)
    tiers = {"csv", "inferred"} | ({"unknown"} if args.include_unknown else set())

    live = kb.current_state()
    if not live:
        sys.exit("knowledge store is empty -- run scan_endpoint.py then build_index.py")

    terms = query_tokens(args.goal, vocab)

    scored = []
    excluded_by_filter = 0
    for record in live.values():
        if not passes_filters(record, exts, args.folder, tiers):
            excluded_by_filter += 1
            continue
        result = score(record, terms)
        if result["score"] < args.min_score:
            continue
        scored.append({
            "path": record["path"],
            "tier": record["tier"],
            "source": record["source"],
            "confidence": record["confidence"],
            "score": result["score"],
            "matched_on": result["matched"],
            "request_id": record.get("evidence", {}).get("request_id", ""),
            "size": record.get("stat", {}).get("size", 0),
            "last_modified": record.get("stat", {}).get("last_modified", ""),
            "metadata": record.get("metadata", {}),
        })

    scored.sort(key=lambda r: (-r["score"], r["path"]))

    # Diversity cap. A single sequencing request can hold hundreds of files
    # that all score identically, which would fill the whole candidate set and
    # hide every other dataset. Keep the best few per request so the agent
    # sees breadth; per_request_total records what was held back.
    kept: List[dict] = []
    per_request: Dict[str, int] = defaultdict(int)
    group_totals: Dict[str, int] = defaultdict(int)
    for row in scored:
        rid = row["request_id"] or "(unattributed)"
        group_totals[rid] += 1
        if per_request[rid] >= args.per_request:
            continue
        if len(kept) >= args.limit:
            continue
        per_request[rid] += 1
        kept.append(row)
    top = kept

    # Group by request so the report can describe a dataset once, not per file.
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for row in top:
        grouped[row["request_id"] or "(unattributed)"].append(row)

    coverage = {}
    if COVERAGE.exists():
        coverage = json.loads(COVERAGE.read_text())

    payload = {
        "goal": args.goal,
        "run_id": kb.new_run_id(),
        "filters": {
            "types": args.types or "all",
            "folders": args.folder or ["(entire scanned scope)"],
            "tiers": sorted(tiers),
            "limit": args.limit,
            "min_score": args.min_score,
        },
        "expanded_terms": sorted(terms),
        "totals": {
            "files_in_store": len(live),
            "excluded_by_filter": excluded_by_filter,
            "above_threshold": len(scored),
            "returned": len(top),
        },
        "groups": [
            {"request_id": rid,
             "files_shown": len(rows),
             "files_matching_total": group_totals.get(rid, len(rows)),
             "files": rows,
             "request_metadata": rows[0]["metadata"] if rid != "(unattributed)" else {}}
            for rid, rows in sorted(
                grouped.items(), key=lambda kv: -max(r["score"] for r in kv[1])
            )
        ],
        "coverage": coverage,
    }

    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("candidates -> {} ({} files, {} groups)".format(
            args.out, len(top), len(grouped)))
    else:
        print(text)


if __name__ == "__main__":
    main()
