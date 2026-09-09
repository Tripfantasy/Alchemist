"""Probe a public accession for everything needed to plan a reanalysis.

METADATA ONLY. This script never downloads a data file, by design: it reads
GEO's text metadata records and the supplementary *directory listing*, and asks
for file sizes with HTTP HEAD (headers, no body). Any attempt to GET a payload
is refused in _fetch_text(), not merely avoided by convention -- the guard is
the point, since the agent driving this script is the thing most likely to try.

What it reports:
  * series title, type, platform, organism, sample count
  * every sample: title, characteristics, library strategy, instrument
  * the supplementary file listing with exact byte sizes
  * the resolved format tier (see workflows/etl_geo.md for the ladder)
  * linked SRA/BioProject accessions, and controlled-access warnings

Usage
-----
  ./.venv/bin/python scripts/geo_probe.py GSE214435
  ./.venv/bin/python scripts/geo_probe.py GSE214435 --out data/GSE214435/probe.json
  ./.venv/bin/python scripts/geo_probe.py GSE214435 --samples-csv data/GSE214435/samples.csv
  ./.venv/bin/python scripts/geo_probe.py GSE214435 --no-sizes   # skip HEAD requests
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

UA = "brew/1.0 (paper reproduction; metadata only)"
GEO_ACC = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"
GEO_FTP = "https://ftp.ncbi.nlm.nih.gov/geo"
MAX_TEXT_BYTES = 8 * 1024 * 1024   # a SOFT record for 500 samples is ~1 MB
THROTTLE_S = 0.4                   # NCBI asks for <=3 req/s unregistered

# Filenames that are payloads, not metadata. GET on these is refused; only HEAD.
PAYLOAD_EXT = (
    ".h5", ".h5ad", ".rds", ".qs", ".loom", ".mtx", ".mtx.gz", ".tar", ".tar.gz",
    ".bam", ".cram", ".fastq", ".fastq.gz", ".fq.gz", ".bw", ".bigwig", ".zip",
    ".csv.gz", ".tsv.gz", ".txt.gz", ".xlsx", ".zarr",
)


class ProbeError(RuntimeError):
    pass


class PayloadRefused(ProbeError):
    """Raised when something asks this script to download actual data."""


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

_last_request = [0.0]


def _throttle() -> None:
    gap = time.time() - _last_request[0]
    if gap < THROTTLE_S:
        time.sleep(THROTTLE_S - gap)
    _last_request[0] = time.time()


def _looks_like_payload(url: str) -> bool:
    path = url.split("?")[0].lower()
    return path.endswith(PAYLOAD_EXT)


def _fetch_text(url: str) -> str:
    """GET a metadata document. Refuses anything that looks like a data file.

    The refusal is deliberate and load-bearing: this project's contract with
    the user is that it probes and plans but never downloads. A guard here is
    checkable; a promise in a prompt is not.
    """
    if _looks_like_payload(url):
        raise PayloadRefused(
            "refusing to download a data file: {}\n"
            "geo_probe is metadata-only. Put the URL in the notebook's ETL "
            "cell and let the user fetch it.".format(url)
        )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    # NCBI returns a transient 502 often enough that one retry is the
    # difference between a working probe and a spurious "does not resolve".
    for attempt in range(3):
        _throttle()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                ctype = resp.headers.get("Content-Type", "")
                if not any(t in ctype for t in ("text", "xml", "json")):
                    raise ProbeError(
                        "unexpected content type {} at {}".format(ctype, url))
                raw = resp.read(MAX_TEXT_BYTES + 1)
            break
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
        except urllib.error.URLError:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    if len(raw) > MAX_TEXT_BYTES:
        raise ProbeError("metadata document over {} MB at {}".format(
            MAX_TEXT_BYTES // 1024 // 1024, url))
    return raw.decode("utf-8", errors="replace")


def _head_size(url: str) -> Optional[int]:
    """Exact byte size from response headers. No body is transferred."""
    _throttle()
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            length = resp.headers.get("Content-Length")
            return int(length) if length else None
    except (urllib.error.URLError, ValueError, OSError):
        return None


# --------------------------------------------------------------------------
# SOFT text parsing
# --------------------------------------------------------------------------

SOFT_LINE = re.compile(r"^!(\w+?)_(\S+)\s*=\s*(.*)$")


def _parse_soft(text: str) -> List[Dict[str, List[str]]]:
    """Split a SOFT text record into per-entity dicts of field -> [values].

    GEO repeats keys (several !Sample_characteristics_ch1 lines, several
    supplementary files), so every field is a list. Callers that want one
    value use _one().
    """
    records: List[Dict[str, List[str]]] = []
    current: Optional[Dict[str, List[str]]] = None
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("^"):
            entity, _, acc = line[1:].partition("=")
            current = defaultdict(list)
            current["_entity"] = [entity.strip()]
            current["_accession"] = [acc.strip()]
            records.append(current)
            continue
        m = SOFT_LINE.match(line)
        if m and current is not None:
            current[m.group(2)].append(m.group(3).strip())
    return records


def _one(rec: Dict[str, List[str]], key: str, default: str = "") -> str:
    vals = rec.get(key) or []
    return vals[0] if vals else default


def _characteristics(rec: Dict[str, List[str]]) -> Dict[str, str]:
    """GEO characteristics are 'key: value' free text. Keep them as-is.

    Never normalize a key into a condition label here -- that mapping is a
    judgment call the agent makes against the paper's figure legends, and
    guessing it silently is how a reanalysis gets its groups backwards.
    """
    out: Dict[str, str] = {}
    for raw in rec.get("characteristics_ch1", []):
        key, sep, val = raw.partition(":")
        if sep:
            out[key.strip().lower()] = val.strip()
        else:
            out.setdefault("_unparsed", raw.strip())
    return out


# --------------------------------------------------------------------------
# supplementary directory listing
# --------------------------------------------------------------------------

class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def _ftp_dir(accession: str) -> str:
    """GEO's FTP layout buckets accessions by their leading digits.

    GSE214435 -> /geo/series/GSE214nnn/GSE214435/suppl/
    GSE1      -> /geo/series/GSEnnn/GSE1/suppl/
    """
    prefix = accession[:3].upper()
    digits = accession[3:]
    kind = {"GSE": "series", "GSM": "samples", "GPL": "platforms"}.get(prefix)
    if kind is None:
        raise ProbeError("no FTP layout known for {}".format(accession))
    bucket = prefix + (digits[:-3] + "nnn" if len(digits) > 3 else "nnn")
    return "{}/{}/{}/{}/suppl/".format(GEO_FTP, kind, bucket, accession)


def _list_suppl(accession: str, want_sizes: bool) -> Tuple[str, List[Dict]]:
    url = _ftp_dir(accession)
    try:
        html = _fetch_text(url)
    except (urllib.error.HTTPError, ProbeError):
        return url, []   # no suppl/ directory at all: a real and common finding

    parser = _LinkParser()
    parser.feed(html)
    files = []
    for href in parser.hrefs:
        if href.startswith(("/", "?", "#")) or href.endswith("/"):
            continue          # parent links, sort links, subdirectories
        if "://" in href:
            continue          # NCBI page-footer links, not files in this directory
        name = urllib.request.unquote(href)
        entry = {"name": name, "url": url + href, "bytes": None}
        if want_sizes:
            entry["bytes"] = _head_size(entry["url"])
        files.append(entry)
    return url, files


# --------------------------------------------------------------------------
# format tier resolution
# --------------------------------------------------------------------------

TIER_RULES = [
    (1, "processed object (authors' own annotations)",
     (".h5ad", ".rds", ".qs", ".loom", ".h5seurat", ".rda", ".rdata")),
    (2, "10x HDF5 matrix", (".h5",)),
    (3, "MTX triplet", ("matrix.mtx", "barcodes.tsv", "features.tsv", "genes.tsv")),
    (4, "count table", (".csv", ".tsv", ".txt", ".xlsx")),
    (5, "alignments", (".bam", ".cram")),
]

# Substrings, matched against lowercased filenames. Keep them stems, not whole
# words: "normalized" misses VoomNormalization, and "peaks" misses
# filtered_peak_bc_matrix.h5 -- both of which are real files in real series.
FLAG_RULES = [
    ("raw matrix (includes empty droplets) -- not the file the paper analyzed",
     ("raw_feature_bc", "raw_gene_bc")),
    ("ATAC/Multiome features, NOT gene expression -- do not load as RNA",
     ("peak", "fragment", "_atac", "atac-")),
    ("normalized values -- NOT valid input to DESeq2/edgeR",
     ("tpm", "fpkm", "rpkm", "normaliz", "cpm", "_scaled", "voom")),
    ("units unstated by the filename: confirm raw counts vs normalized from the "
     "file header before any DE", ("processed", ".dge.")),
    ("series-level bundle: extract before use, and this is the real download cost",
     (".tar",)),
    ("legacy CellRanger naming (genes.tsv is 2-column; features.tsv is 3) -- "
     "loaders are version-sensitive", ("genes.tsv",)),
    ("spatial assay", ("spatial", "visium", "tissue_positions")),
    ("antibody/CITE-seq or hashing features alongside RNA -- split by feature "
     "type first", ("_adt", "antibody", "hto", "citeseq", "cite-seq")),
]


def _file_tier(name: str) -> Optional[int]:
    low = name.lower()
    for tier, _desc, patterns in TIER_RULES:
        if any(p in low for p in patterns):
            return tier
    return None


def _resolve_tier(files: List[Dict], has_sra: bool) -> Dict:
    names = [f["name"].lower() for f in files]

    # Per file, not just per series. A multi-assay deposit has a tier per
    # modality, and "the highest tier present" can point at a completely
    # different assay than the target figure -- e.g. a bulk .rda outranking the
    # snRNA .h5 you actually want.
    per_file = {f["name"]: _file_tier(f["name"]) for f in files}
    tiers_present = sorted({t for t in per_file.values() if t})

    tier, label = None, None
    for candidate, desc, patterns in TIER_RULES:
        if any(p in n for n in names for p in patterns):
            tier, label = candidate, desc
            break
    if tier is None:
        tier, label = (6, "FASTQ via SRA only") if has_sra else (None, "nothing deposited")

    # Name the files that triggered each flag. A caveat the agent cannot trace
    # to a filename gets copied into a report as vague hedging.
    flags: List[Dict] = []
    for msg, patterns in FLAG_RULES:
        hits = [f["name"] for f, n in zip(files, names)
                if any(p in n for p in patterns)]
        if hits:
            flags.append({"note": msg, "files": hits})
    if tier == 2 and not any("filtered" in n for n in names):
        flags.append({"note": "no 'filtered' in any .h5 name -- confirm filtered "
                              "vs raw before trusting cell counts", "files": []})
    if tier == 1:
        flags.append({"note": "Tier 1 carries the authors' conclusions, not just "
                              "their data -- rebuild from Tier 2/3 counts to "
                              "verify their pipeline", "files": []})
    if len(tiers_present) > 1:
        flags.append({
            "note": "files span tiers {} -- the highest tier is not necessarily "
                    "your target. Pick by modality and by which figure you are "
                    "reproducing, not by tier alone."
                    .format(", ".join(str(t) for t in tiers_present)),
            "files": [],
        })
    return {"tier": tier, "label": label, "flags": flags,
            "tiers_present": tiers_present, "by_file": per_file}


# --------------------------------------------------------------------------
# processing state
# --------------------------------------------------------------------------
#
# Whether the deposit has ALREADY had cell-calling and QC filtering applied.
# This decides the shape of the reproduction: re-running a QC step over an
# already-filtered matrix double-filters it, and the notebook then reports a
# cell count below the paper's for a reason no one can see. See
# workflows/etl_geo.md Step 2b -- the agent branches on `state` to decide
# whether QC cells ship live or commented.
#
# Filename evidence only, plus whatever the series text asserts. This is an
# inference, never a fact: the file header is the only proof, and reading it
# means downloading, which this project does not do. `state` therefore feeds an
# [inferred] tier step -- never a `stated` one.

PROCESSED_PATTERNS = (
    "filtered_feature_bc", "filtered_gene_bc", "filtered_peak_bc",
    "_filtered", "filtered_", "_qc", "qc_", "postqc", "post_qc",
    "_clean", "cleaned", "_singlet", "singlets", "doubletfilt",
    "_annotated", "annotation", "celltype", "cell_type", "_metadata",
    "_clusters", "_umap", "_tsne", "_seurat", "_processed",
)

# NOT a bare "_raw" here. GEO names EVERY series-level bundle "<GSE>_RAW.tar"
# as a naming convention, whatever is inside it -- GSE252365_RAW.tar holds
# processed count tables. A bare "_raw." pattern classified that series as raw
# droplets and would have shipped a full QC section against already-filtered
# data. Match the CellRanger matrix names and explicit count-table names only.
RAW_PATTERNS = ("raw_feature_bc", "raw_gene_bc", "unfiltered",
                "raw_count", "rawcount", "_raw_matrix", "raw_umi")

# The GEO bundle convention, which tells you nothing about processing state.
BUNDLE_RE = re.compile(r"_raw\.tar(\.gz)?$", re.I)

# Series-text assertions. Matched against summary + overall_design, lowercased.
PROCESSED_TEXT = (
    "after quality control", "after qc", "quality-control filtered",
    "low-quality cells were removed", "cells were filtered",
    "doublets were removed", "doublet removal", "filtered to retain",
    "passing quality control", "post-quality-control",
)


def _resolve_processing(files: List[Dict], fmt: Dict, text: str) -> Dict:
    """Infer whether the deposited matrices are already QC-filtered.

    Returns state in {processed, raw, mixed, unknown} plus the evidence that
    produced it, so a report can cite a filename instead of hedging.
    """
    names = [f["name"] for f in files]
    low = text.lower()

    # A bundle hides its contents, so it can carry neither kind of evidence.
    bundles = [n for n in names if BUNDLE_RE.search(n)]
    visible = [n for n in names if n not in bundles]

    proc_hits = [n for n in visible
                 if any(p in n.lower() for p in PROCESSED_PATTERNS)]
    raw_hits = [n for n in visible
                if any(p in n.lower() for p in RAW_PATTERNS)]
    text_hits = [p for p in PROCESSED_TEXT if p in low]

    # A Tier 1 object is processed by definition -- it carries the authors'
    # clustering, which cannot exist before their QC ran.
    tier1 = [n for n, t in (fmt.get("by_file") or {}).items() if t == 1]

    processed = bool(proc_hits or tier1 or text_hits)
    raw = bool(raw_hits)

    if processed and raw:
        state = "mixed"
    elif processed:
        state = "processed"
    elif raw:
        state = "raw"
    else:
        state = "unknown"

    evidence = []
    if tier1:
        evidence.append({"signal": "tier-1 object carries the authors' own "
                                   "clustering, so their QC already ran",
                         "files": tier1})
    if proc_hits:
        evidence.append({"signal": "filename indicates cell-called or "
                                   "QC-filtered output", "files": proc_hits})
    if raw_hits:
        evidence.append({"signal": "filename indicates raw droplets, "
                                   "pre-cell-calling", "files": raw_hits})
    if text_hits:
        evidence.append({"signal": "series text asserts QC was applied "
                                   "upstream: \"{}\"".format(text_hits[0]),
                         "files": []})
    if bundles and state == "unknown":
        evidence.append({"signal": "contents hidden inside a GEO _RAW.tar "
                                   "bundle -- the name is a GEO convention, "
                                   "NOT a statement that the data is raw. "
                                   "List the archive before deciding",
                         "files": bundles})

    guidance = {
        "processed": "QC/filtering appears ALREADY APPLIED. Ship the QC cells "
                     "COMMENTED, with the paper's thresholds recorded in them "
                     "and a note on when to uncomment. Re-running them here "
                     "double-filters and silently undercounts cells.",
        "raw": "Raw droplets. QC cells ship LIVE -- cell-calling and filtering "
               "are genuinely part of this reproduction.",
        "mixed": "BOTH raw and processed files are deposited. Decide by target "
                 "figure, not by tier: start from raw to verify the authors' "
                 "pipeline, from processed to build on their result. Say which "
                 "you chose and why.",
        "unknown": "No filename or series-text signal either way. Ship QC cells "
                   "LIVE but flag the uncertainty: the first ETL cell should "
                   "print matrix dimensions, and a cell count already close to "
                   "the paper's post-QC number means the deposit was filtered "
                   "and the QC cells must be commented out.",
    }[state]

    return {"state": state, "evidence": evidence, "guidance": guidance,
            "inferred": True}


# --------------------------------------------------------------------------
# probe
# --------------------------------------------------------------------------

def _relations(rec: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """!Series_relation lines carry the SRA/BioProject links and reanalysis pointers."""
    out: Dict[str, List[str]] = defaultdict(list)
    for raw in rec.get("relation", []):
        kind, _, value = raw.partition(":")
        out[kind.strip()].append(value.strip())
    return dict(out)


def probe_series(accession: str, want_sizes: bool = True) -> Dict:
    acc = accession.strip().upper()
    if not re.fullmatch(r"GSE\d+", acc):
        raise ProbeError(
            "expected a GEO series (GSE#####), got {}.\n"
            "GSM/SRP/PRJNA/E-MTAB and Zenodo DOIs are resolved by hand -- see "
            "resources/geo_reference.md for the URL patterns.".format(accession))

    self_text = _fetch_text(
        "{}?acc={}&targ=self&form=text&view=brief".format(GEO_ACC, acc))
    if "could not be found" in self_text.lower() or not self_text.startswith("^"):
        raise ProbeError(
            "{} does not resolve. Embargoed or mistyped accessions are common in "
            "accepted-but-unpublished papers -- report this as an inaccessible "
            "asset rather than working around it.".format(acc))
    series = _parse_soft(self_text)[0]

    # One request returns every sample record, so don't loop over GSMs.
    sample_text = _fetch_text(
        "{}?acc={}&targ=gsm&form=text&view=brief".format(GEO_ACC, acc))
    samples = []
    for rec in _parse_soft(sample_text):
        if _one(rec, "_entity") != "SAMPLE":
            continue
        chars = _characteristics(rec)
        samples.append({
            "gsm": _one(rec, "_accession") or _one(rec, "geo_accession"),
            "title": _one(rec, "title"),
            "organism": _one(rec, "organism_ch1"),
            "library_strategy": _one(rec, "library_strategy"),
            "instrument": _one(rec, "instrument_model"),
            "characteristics": chars,
            # GEO writes the literal "NONE" when a sample has no file of its
            # own; carrying that through produces a sample sheet pointing at a
            # file called NONE.
            "suppl_files": [v for k, vals in rec.items()
                            if k.startswith("supplementary_file")
                            for v in vals if v.strip().upper() != "NONE"],
        })

    suppl_url, files = _list_suppl(acc, want_sizes)
    relations = _relations(series)
    has_sra = any("SRA" in k for k in relations)

    declared = len(series.get("sample_id", []))
    result = {
        "accession": acc,
        "title": _one(series, "title"),
        "summary": " ".join(series.get("summary", []))[:1200],
        "overall_design": " ".join(series.get("overall_design", []))[:1200],
        "types": series.get("type", []),
        "platforms": series.get("platform_id", []),
        "pubmed_ids": series.get("pubmed_id", []),
        "sample_count": max(declared, len(samples)),
        "samples": samples,
        "suppl_url": suppl_url,
        "suppl_files": files,
        "suppl_total_bytes": sum(f["bytes"] or 0 for f in files) or None,
        "relations": relations,
        "sub_series": relations.get("SuperSeries of", []),
        "format": _resolve_tier(files, has_sra),
        "warnings": [],
        "probed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    result["processing"] = _resolve_processing(
        files, result["format"],
        "{} {}".format(result["summary"], result["overall_design"]))

    if len(result["types"]) > 1:
        result["warnings"].append(
            "multi-assay series ({}). Select files by modality -- an ATAC peak "
            "matrix and an RNA gene matrix look alike in a listing."
            .format("; ".join(result["types"])))
    organisms = sorted({s["organism"] for s in samples if s["organism"]})
    if len(organisms) > 1:
        result["warnings"].append(
            "multiple organisms ({}). Split by organism before anything else, "
            "and mind gene-symbol case (Gfap vs GFAP)."
            .format(", ".join(organisms)))
    if declared and len(samples) and declared != len(samples):
        result["warnings"].append(
            "series declares {} samples but {} sample records parsed -- resolve "
            "before building the sample sheet".format(declared, len(samples)))
    if result["sub_series"]:
        result["warnings"].append(
            "SuperSeries: files live in the sub-series ({}), not here. Probe "
            "each one.".format(", ".join(result["sub_series"])))
    if not files:
        result["warnings"].append(
            "no supplementary files at the series level -- check the individual "
            "GSMs (per-sample suppl_files above) before concluding none exist")
    if has_sra and result["format"]["tier"] in (None, 6):
        result["warnings"].append(
            "raw reads only. Descending to Tier 6 costs days of compute and "
            "hundreds of GB -- justify it explicitly in the report.")
    if any(re.search(r"phs\d{6}|dbgap|EGAS\d+", v, re.I)
           for vals in relations.values() for v in vals):
        result["warnings"].append(
            "controlled-access component detected: reproduction is blocked until "
            "a data-use agreement clears. Report the application route.")
    return result


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def _human(n: Optional[int]) -> str:
    if not n:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "{:.1f} {}".format(n, unit)
        n /= 1024.0
    return "?"


def print_summary(p: Dict) -> None:
    print("\n{}  {}".format(p["accession"], p["title"]))
    print("  type      : {}".format("; ".join(p["types"]) or "?"))
    print("  platform  : {}".format(", ".join(p["platforms"]) or "?"))
    print("  samples   : {}".format(p["sample_count"]))
    if p["pubmed_ids"]:
        print("  pubmed    : {}".format(", ".join(p["pubmed_ids"])))

    fmt = p["format"]
    print("\n  format tier: {} -- {}".format(fmt["tier"] or "none", fmt["label"]))
    for flag in fmt["flags"]:
        print("    ! {}".format(flag["note"]))
        for name in flag["files"][:4]:
            print("        {}".format(name))

    proc = p.get("processing") or {}
    if proc:
        print("\n  processing state: {}  [inferred from filenames/series text]"
              .format(proc["state"].upper()))
        for ev in proc["evidence"]:
            print("    - {}".format(ev["signal"]))
            for name in ev["files"][:4]:
                print("        {}".format(name))
        print("    => {}".format(proc["guidance"]))

    print("\n  supplementary files ({}, {}):".format(
        len(p["suppl_files"]), _human(p["suppl_total_bytes"])))
    by_file = fmt.get("by_file", {})
    for f in p["suppl_files"][:25]:
        tier_of = by_file.get(f["name"])
        print("    {:<54} {:>9}  {}".format(
            f["name"][:54], _human(f["bytes"]),
            "T{}".format(tier_of) if tier_of else "--"))
    if len(p["suppl_files"]) > 25:
        print("    ... {} more".format(len(p["suppl_files"]) - 25))

    print("\n  samples:")
    for s in p["samples"][:12]:
        chars = ", ".join("{}={}".format(k, v) for k, v in
                          list(s["characteristics"].items())[:4])
        print("    {}  {:<28} {}".format(s["gsm"], s["title"][:28], chars[:70]))
    if len(p["samples"]) > 12:
        print("    ... {} more".format(len(p["samples"]) - 12))

    for kind, values in p["relations"].items():
        print("  relation  : {} -> {}".format(kind, ", ".join(values)))
    for w in p["warnings"]:
        print("\n  WARNING: {}".format(w))
    print("\n  Next: map samples to the paper's conditions by hand "
          "(workflows/etl_geo.md, Step 3). No file was downloaded.\n")


def write_samples_csv(p: Dict, path: Path) -> None:
    """Write a DRAFT sample sheet. condition is left blank on purpose.

    Filling condition from GEO titles automatically is exactly the mistake
    workflows/etl_geo.md Step 3 warns about -- the mapping has to be checked
    against the paper's figure legends and n-per-group.
    """
    keys: List[str] = []
    for s in p["samples"]:
        for k in s["characteristics"]:
            if k not in keys:
                keys.append(k)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["gsm", "title", "condition", "replicate", "file"]
                   + ["char_" + k for k in keys] + ["library_strategy"])
        for s in p["samples"]:
            w.writerow([s["gsm"], s["title"], "", "",
                        (s["suppl_files"][0].rsplit("/", 1)[-1]
                         if s["suppl_files"] else "")]
                       + [s["characteristics"].get(k, "") for k in keys]
                       + [s["library_strategy"]])
    print("  draft sample sheet -> {}  (fill `condition` against the paper's "
          "figure legends)".format(path))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accession", help="GEO series accession, e.g. GSE214435")
    ap.add_argument("--out", type=Path, help="write the full probe as JSON")
    ap.add_argument("--samples-csv", type=Path,
                    help="write a draft sample sheet (condition left blank)")
    ap.add_argument("--no-sizes", action="store_true",
                    help="skip HEAD requests for file sizes (faster, no byte counts)")
    args = ap.parse_args()

    try:
        p = probe_series(args.accession, want_sizes=not args.no_sizes)
    except ProbeError as e:
        sys.exit("probe failed: {}".format(e))
    except urllib.error.URLError as e:
        sys.exit("network error: {}".format(e))

    print_summary(p)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(p, indent=2), encoding="utf-8")
        print("  probe -> {}".format(args.out))
    if args.samples_csv:
        write_samples_csv(p, args.samples_csv)


if __name__ == "__main__":
    main()
