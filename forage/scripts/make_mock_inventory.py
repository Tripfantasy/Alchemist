"""Synthesize a plausible inventory so the pipeline is testable without Globus.

Builds a fake collection tree from the metadata CSV, deliberately reproducing
the conditions the agent must survive:

  - paths are RE-ROOTED (/lab_data/... not /n/analysis/<lab>/...), so anything
    that matched on full paths would break here and only token matching works
  - some requests get no files at all, exercising the "indexed but absent" gap
  - some folders carry no MOLNG id, exercising vocabulary inference
  - some folders are deliberately vague ("new_data/final2"), which must land in
    the 'unknown' tier rather than being over-interpreted

Deterministic: seeded, so repeated runs produce an identical tree.

  python3 scripts/make_mock_inventory.py --out knowledge/inventory.mock.jsonl
"""

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Real metadata if present, else the synthetic example. metadata.csv
# carries named requesters and internal paths, so it is gitignored and never
# ships; metadata_example.csv has the same 35 columns with synthetic rows, so a
# fresh clone can build the mock tree without it.
METADATA_CSV = ROOT / "resources" / "metadata.csv"
if not METADATA_CSV.exists():
    METADATA_CSV = ROOT / "resources" / "metadata_example.csv"

FASTQ_PER_RUN = ["_S1_L001_R1_001.fastq.gz", "_S1_L001_R2_001.fastq.gz"]
TENX_OUTPUT = [
    "outs/filtered_feature_bc_matrix.h5",
    "outs/raw_feature_bc_matrix.h5",
    "outs/web_summary.html",
    "outs/metrics_summary.csv",
    "outs/possorted_genome_bam.bam",
]
BULK_OUTPUT = ["counts/gene_counts.tsv", "qc/multiqc_report.html", "align/sample.bam"]

# Folders with real biological meaning but no MOLNG anchor -> inference tier.
INFERENCE_TREE = [
    ("/lab_data/reanalysis/sc_OE_h19/", ["analysis.rmd", "seurat_obj.rds",
                                       "deg_table.csv", "umap.pdf"]),
    ("/lab_data/reanalysis/snRNA_VNO_adult_wt/", ["integrated.h5ad", "markers.tsv"]),
    ("/lab_data/reanalysis/slideseq_OB_p7_development/", ["puck_matrix.mtx.gz",
                                                        "spatial_coords.csv"]),
    ("/lab_data/reanalysis/apoe4_vs_apoe3_organoid_multiome/", ["grn_edges.tsv",
                                                              "atac_peaks.bed"]),
    ("/lab_data/imaging/xenium_MOE_criticalperiod_p12/", ["cells.zarr",
                                                        "transcripts.parquet"]),
    ("/lab_data/reference/mm10/", ["genome.fa", "genes.gtf"]),
]

# Deliberately meaningless -> must be refused as 'unknown'.
VAGUE_TREE = [
    ("/lab_data/new_data/final2/", ["output.csv", "results.txt", "copy_of_thing.xlsx"]),
    ("/lab_data/tmp/backup/v3/", ["data.bam", "misc.json"]),
    ("/lab_data/scratch/", ["test.py", "notes.txt"]),
]


def load_rows():
    with METADATA_CSV.open(newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("Request #") or "").strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "knowledge" / "inventory.mock.jsonl"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--skip-fraction", type=float, default=0.25,
                    help="fraction of pathed requests to leave absent")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = load_rows()
    records = []

    header = {
        "kind": "scan_meta",
        "ts": kb.utc_now(),
        "run_id": "run-mock",
        "collection_id": "00000000-mock-0000-0000-000000000000",
        "collection_name": "MOCK Example Lab Collection",
        "roots": ["/lab_data/"],
        "depth": 8,
        "types": [],
        "exclude": [],
    }

    dirs = set()

    def add_file(path, size):
        parent = path.rsplit("/", 1)[0] + "/"
        parts = parent.strip("/").split("/")
        for i in range(1, len(parts) + 1):
            dirs.add("/" + "/".join(parts[:i]) + "/")
        records.append({
            "kind": "file",
            "path": path,
            "name": path.rsplit("/", 1)[-1],
            "ext": kb._ext(path.rsplit("/", 1)[-1]),
            "size": size,
            "last_modified": "2024-11-0{} 12:00:00+00:00".format(rng.randint(1, 9)),
            "depth": path.count("/") - 1,
            "anchors": kb.extract_anchors(path),
        })

    skipped = []
    for row in rows:
        rid = row["Request #"].strip().upper()
        raw_paths = (row.get("Flowcell Result Paths") or "").strip()
        if not raw_paths:
            skipped.append((rid, "no path in csv"))
            continue
        if rng.random() < args.skip_fraction:
            skipped.append((rid, "simulated absent from endpoint"))
            continue

        ptype = (row.get("Project Type") or "").lower()
        for chunk in raw_paths.split(","):
            segs = [s for s in chunk.strip().split("/") if s]
            if len(segs) < 2:
                continue
            flowcell = segs[-1]
            user = segs[-3] if len(segs) >= 3 else "unknown"
            # RE-ROOTED: the /n/analysis prefix is gone, as after a real transfer
            base = "/lab_data/sequencing/{}/{}/{}/".format(user, rid, flowcell)

            for suffix in FASTQ_PER_RUN:
                add_file(base + "fastq/" + rid + suffix, rng.randint(2, 9) * 10**9)
            outputs = TENX_OUTPUT if "10x" in ptype or "scrna" in ptype else BULK_OUTPUT
            for rel in outputs:
                add_file(base + rel, rng.randint(1, 6) * 10**8)

    for folder, names in INFERENCE_TREE + VAGUE_TREE:
        for name in names:
            add_file(folder + name, rng.randint(1, 900) * 10**6)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, sort_keys=True) + "\n")
        for d in sorted(dirs):
            fh.write(json.dumps({"kind": "dir", "path": d,
                                 "name": d.strip("/").split("/")[-1],
                                 "depth": d.count("/") - 2}, sort_keys=True) + "\n")
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    print("mock inventory -> {}".format(out))
    print("  files: {} | dirs: {}".format(len(records), len(dirs)))
    print("  requests represented: {} | absent: {}".format(
        len(rows) - len(skipped), len(skipped)))
    no_path = sum(1 for _, why in skipped if why == "no path in csv")
    print("    of which {} had no path in the CSV, {} simulated absent".format(
        no_path, len(skipped) - no_path))


if __name__ == "__main__":
    main()
