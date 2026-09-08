"""Recursive, READ-ONLY inventory of a Globus collection.

Walks the collection with operation_ls and writes one JSON object per entry to
a cache file, so later index/report runs never re-hit the API.

Safety
------
CLAUDE.md: "Only read the files in the globus directories, NEVER edit, move, or
copy files under any circumstances."

That rule is enforced here rather than merely honoured. ReadOnlyTransferClient
below overrides every mutating TransferClient method with a raised error, so a
future edit to this repo -- by a person or an agent -- cannot make this script
write to the collection without first deleting the guard on purpose.

Usage
-----
  python3 scripts/scan_endpoint.py <collection-uuid> \
      --path /projects/yu/ --depth 6 --out knowledge/inventory.jsonl

  # restrict to specific subfolders
  python3 scripts/scan_endpoint.py <uuid> --path /a/ --path /b/
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set

import globus_sdk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402
from globus_auth import ensure_consent, get_transfer_client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "knowledge" / "inventory.jsonl"

# Every TransferClient method that can change remote state.
FORBIDDEN = (
    "submit_transfer",
    "submit_delete",
    "operation_mkdir",
    "operation_rename",
    "operation_symlink",
    "delete_endpoint",
    "create_endpoint",
    "update_endpoint",
    "add_endpoint_acl_rule",
    "delete_endpoint_acl_rule",
    "update_endpoint_acl_rule",
    "make_submit_transfer_data",
)


class ReadOnlyViolation(RuntimeError):
    pass


class ReadOnlyTransferClient:
    """Proxy that permits only read operations against a collection."""

    def __init__(self, inner: globus_sdk.TransferClient):
        self._inner = inner

    def __getattr__(self, name: str):
        if name in FORBIDDEN:
            raise ReadOnlyViolation(
                "{}() is blocked: this agent is read-only on Globus "
                "collections (see CLAUDE.md).".format(name)
            )
        return getattr(self._inner, name)


def walk(
    client: ReadOnlyTransferClient,
    collection_id: str,
    roots: List[str],
    max_depth: int,
    exts: Optional[Set[str]] = None,
    exclude: Optional[List[str]] = None,
    max_entries: int = 0,
    sleep: float = 0.0,
) -> Iterator[dict]:
    """Breadth-first walk yielding one record per file and directory."""
    exclude = [e.lower() for e in (exclude or [])]
    queue = [(r if r.endswith("/") else r + "/", 0) for r in roots]
    seen_dirs: Set[str] = set()
    emitted = 0
    errors = 0

    while queue:
        path, depth = queue.pop(0)
        if path in seen_dirs:
            continue
        seen_dirs.add(path)

        try:
            listing = client.operation_ls(collection_id, path=path)
        except globus_sdk.TransferAPIError as err:
            errors += 1
            # A permission-denied subtree is a finding, not a crash -- record
            # it so the gap analysis can report what could not be seen.
            yield {
                "kind": "error",
                "path": path,
                "code": err.code,
                "message": str(err.message)[:300],
            }
            continue

        for item in listing:
            name = item["name"]
            full = path + name
            if any(x in full.lower() for x in exclude):
                continue

            if item["type"] == "dir":
                if depth < max_depth:
                    queue.append((full + "/", depth + 1))
                yield {
                    "kind": "dir",
                    "path": full + "/",
                    "name": name,
                    "depth": depth,
                }
                continue

            if item["type"] != "file":
                continue  # skip invalid_symlink and friends

            ext = kb._ext(name)
            if exts and ext not in exts:
                continue

            emitted += 1
            yield {
                "kind": "file",
                "path": full,
                "name": name,
                "ext": ext,
                "size": item.get("size", 0),
                "last_modified": item.get("last_modified", ""),
                "depth": depth,
                "anchors": kb.extract_anchors(full),
            }

            if max_entries and emitted >= max_entries:
                print("scan: hit --max-entries {}, stopping".format(max_entries))
                queue = []
                break

        if len(seen_dirs) % 250 == 0:
            # long walks are otherwise silent for tens of minutes
            print("scan: {} dirs visited, {} queued, {} files, {} unreadable".format(
                len(seen_dirs), len(queue), emitted, errors), flush=True)

        if sleep:
            time.sleep(sleep)

    print("scan: {} files, {} dirs visited, {} unreadable".format(
        emitted, len(seen_dirs), errors), flush=True)


def load_type_groups(names: List[str]) -> Optional[Set[str]]:
    if not names:
        return None
    vocab = json.loads((ROOT / "resources" / "vocab.json").read_text())
    groups = vocab["type_groups"]
    exts: Set[str] = set()
    for n in names:
        n = n.strip().lower()
        if n in groups:
            exts.update(groups[n])
        elif n.startswith("."):
            exts.add(n)
        else:
            sys.exit(
                "unknown type group {!r}; choose from {} or pass a .ext".format(
                    n, ", ".join(sorted(groups))
                )
            )
    return exts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("collection", help="Globus collection / endpoint UUID")
    ap.add_argument("--path", action="append", default=[],
                    help="root path to scan; repeatable (default: /)")
    ap.add_argument("--depth", type=int, default=8, help="max recursion depth")
    ap.add_argument("--types", default="",
                    help="comma-separated type groups (neuroimaging,sequencing,"
                         "omics,tabular,docs,code) or explicit .exts")
    ap.add_argument("--exclude", action="append", default=[],
                    help="skip paths containing this substring; repeatable")
    ap.add_argument("--max-entries", type=int, default=0, help="stop after N files")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds between directory listings (be kind to the API)")
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "confidential", "native"],
                    help="auth mode; confidential is preferred (its identity can "
                         "be granted read-only on the collection)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    roots = args.path or ["/"]
    exts = load_type_groups([t for t in args.types.split(",") if t.strip()])

    raw = get_transfer_client(collection_id=args.collection, mode=args.mode)
    raw = ensure_consent(raw, args.collection, roots[0], mode=args.mode)
    client = ReadOnlyTransferClient(raw)

    info = client.get_endpoint(args.collection)
    print("collection: {} [{}]".format(info["display_name"], info["entity_type"]))
    print("roots: {} | depth: {} | types: {}".format(
        ", ".join(roots), args.depth, ",".join(sorted(exts)) if exts else "all"))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "kind": "scan_meta",
        "ts": kb.utc_now(),
        "run_id": kb.new_run_id(),
        "collection_id": args.collection,
        "collection_name": info["display_name"],
        "roots": roots,
        "depth": args.depth,
        "types": sorted(exts) if exts else [],
        "exclude": args.exclude,
    }
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, sort_keys=True) + "\n")
        for rec in walk(client, args.collection, roots, args.depth, exts,
                        args.exclude, args.max_entries, args.sleep):
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    print("inventory -> {}".format(out))


if __name__ == "__main__":
    main()
