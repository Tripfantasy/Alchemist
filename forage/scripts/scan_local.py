"""Recursive, READ-ONLY inventory of a local or mounted directory tree.

The local-filesystem counterpart of scan_endpoint.py, for data that is already
reachable as a path (a NAS mount, a lab server, a local disk) rather than
through a Globus collection. It writes the same inventory records, so
build_index.py, search.py, zip_index.py --find and everything downstream work
on its output unchanged.

Safety
------
CLAUDE.md: "Only read the files in the globus directories, NEVER edit, move, or
copy files under any circumstances." The rule applies to local data too.

There is no server here to reject a write, so the binding guarantee has to come
from how the data is reached: a read-only mount, or a user account that can
only read it. This script checks for that before walking and REFUSES a root it
could write to unless --allow-writable is passed, which the researcher has to
approve. What it found is recorded in the scan_meta header.

The backstop is the code itself: the walk uses only os.scandir and stat. It
never opens a file, not even to read it.

Roots
-----
If resources/site.json lists `local_roots`, a scan with no --path covers those
roots, and every --path must lie inside one of them. That keeps a mistyped
path from walking a whole disk.

Usage
-----
  # Is each configured root read-only? (no walk)
  ./.venv/bin/python scripts/scan_local.py --check

  # Survey the top of the tree
  ./.venv/bin/python scripts/scan_local.py --depth 2 --out knowledge/survey.jsonl

  # Scan the agreed scope
  ./.venv/bin/python scripts/scan_local.py --path /mnt/lab/projects/ \
      --depth 5 --exclude /backup/ --out knowledge/inventory.jsonl
"""

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402
from scan_endpoint import load_type_groups  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "knowledge" / "inventory.jsonl"


class WritableRoot(RuntimeError):
    pass


def default_label() -> str:
    """The collection_id recorded for local scans.

    kb.file_key() hashes collection_id with the path, so this namespaces local
    records apart from any Globus collection's. Set `local_label` in site.json
    when the same mount is scanned from more than one host.
    """
    return kb.SITE.get("local_label") or "local:" + socket.gethostname()


def configured_roots() -> List[str]:
    return [_dir(r) for r in kb.SITE.get("local_roots", [])]


def _dir(path: str) -> str:
    p = os.path.abspath(os.path.expanduser(path))
    return p if p.endswith("/") else p + "/"


def write_access(path: str) -> str:
    """How this process could write under `path`: 'none' or the reason it can.

    A read-only mount is the strongest answer: nothing on it can change,
    whatever the account. Otherwise the account's own permission on the root
    decides. Subdirectories can differ from the root, so this is a check of
    the setup, not a proof for every file below it.
    """
    try:
        if os.statvfs(path).f_flag & os.ST_RDONLY:
            return "none"
    except OSError:
        pass
    return "account can write" if os.access(path, os.W_OK) else "none"


def guard(roots: List[str], allow_writable: bool) -> Dict[str, str]:
    status = {r: write_access(r) for r in roots}
    writable = [r for r, s in status.items() if s != "none"]
    if writable and not allow_writable:
        raise WritableRoot(
            "this account can write to:\n  {}\n"
            "forage only reads, but on a local path nothing outside this code "
            "enforces that.\nPrefer a read-only mount (mount -o ro, or a "
            "read-only bind mount). To scan anyway,\nthe researcher must approve "
            "it; then pass --allow-writable.".format("\n  ".join(writable)))
    return status


def _mtime(ts: float) -> str:
    # Same shape Globus returns, so last_modified sorts and slices alike.
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")


def walk(
    roots: List[str],
    max_depth: int,
    exts: Optional[Set[str]] = None,
    exclude: Optional[List[str]] = None,
    max_entries: int = 0,
) -> Iterator[dict]:
    """Breadth-first walk yielding one record per file and directory.

    Depth counts as in scan_endpoint.walk: entries directly inside a root are
    depth 0. Symlinked directories are not followed (they can loop or leave
    the scope); symlinked files are recorded with their target's size.
    """
    exclude = [e.lower() for e in (exclude or [])]
    queue = [(r, 0) for r in roots]
    seen_dirs: Set[str] = set()
    emitted = 0
    errors = 0
    skipped_links = 0

    while queue:
        path, depth = queue.pop(0)
        if path in seen_dirs:
            continue
        seen_dirs.add(path)

        try:
            with os.scandir(path) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError as err:
            errors += 1
            # An unreadable subtree is a finding, not a crash -- record it so
            # the gap analysis can report what could not be seen.
            yield {
                "kind": "error",
                "path": path,
                "code": type(err).__name__,
                "message": str(err)[:300],
            }
            continue

        for entry in entries:
            name = entry.name
            full = path + name
            if any(x in full.lower() for x in exclude):
                continue

            try:
                if entry.is_dir(follow_symlinks=False):
                    if depth < max_depth:
                        queue.append((full + "/", depth + 1))
                    yield {
                        "kind": "dir",
                        "path": full + "/",
                        "name": name,
                        "depth": depth,
                    }
                    continue
                if entry.is_symlink() and entry.is_dir():
                    skipped_links += 1
                    continue
                if not entry.is_file():
                    continue  # broken links, sockets, devices
                st = entry.stat()
            except OSError:
                errors += 1
                continue

            ext = kb._ext(name)
            if exts and ext not in exts:
                continue

            emitted += 1
            yield {
                "kind": "file",
                "path": full,
                "name": name,
                "ext": ext,
                "size": st.st_size,
                "last_modified": _mtime(st.st_mtime),
                "depth": depth,
                "anchors": kb.extract_anchors(full),
            }

            if max_entries and emitted >= max_entries:
                print("scan: hit --max-entries {}, stopping".format(max_entries))
                queue = []
                break

        if len(seen_dirs) % 2000 == 0:
            print("scan: {} dirs visited, {} queued, {} files, {} unreadable".format(
                len(seen_dirs), len(queue), emitted, errors), flush=True)

    print("scan: {} files, {} dirs visited, {} unreadable, {} directory links "
          "not followed".format(emitted, len(seen_dirs), errors, skipped_links), flush=True)


def resolve_roots(paths: List[str]) -> List[str]:
    configured = configured_roots()
    roots = [_dir(p) for p in paths] or configured
    if not roots:
        sys.exit("no roots: pass --path, or set local_roots in resources/site.json")
    for r in roots:
        if not os.path.isdir(r):
            sys.exit("not a directory: {}".format(r))
    if configured:
        outside = [r for r in roots if not any(r.startswith(c) for c in configured)]
        if outside:
            sys.exit("outside site.json local_roots ({}):\n  {}".format(
                ", ".join(configured), "\n  ".join(outside)))
    return roots


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", action="append", default=[],
                    help="directory to scan; repeatable (default: site.json local_roots)")
    ap.add_argument("--depth", type=int, default=8, help="max recursion depth")
    ap.add_argument("--types", default="",
                    help="comma-separated type groups (neuroimaging,sequencing,"
                         "omics,tabular,docs,code) or explicit .exts")
    ap.add_argument("--exclude", action="append", default=[],
                    help="skip paths containing this substring; repeatable")
    ap.add_argument("--max-entries", type=int, default=0, help="stop after N files")
    ap.add_argument("--label", default=None,
                    help="collection_id to record (default: site.json local_label, "
                         "else local:<hostname>)")
    ap.add_argument("--allow-writable", action="store_true",
                    help="scan roots this account can write to; needs the "
                         "researcher's approval")
    ap.add_argument("--check", action="store_true",
                    help="report whether each root is read-only, then exit")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    roots = resolve_roots(args.path)

    if args.check:
        for r in roots:
            state = write_access(r)
            print("  {:<8} {}".format("ok" if state == "none" else "WRITABLE", r))
            if state != "none":
                print("           {}".format(state))
        return

    try:
        access = guard(roots, args.allow_writable)
    except WritableRoot as err:
        sys.exit("REFUSED  " + str(err))

    exts = load_type_groups([t for t in args.types.split(",") if t.strip()])
    label = args.label or default_label()
    print("local: {} | roots: {} | depth: {} | types: {}".format(
        label, ", ".join(roots), args.depth,
        ",".join(sorted(exts)) if exts else "all"))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "kind": "scan_meta",
        "backend": "local",
        "ts": kb.utc_now(),
        "run_id": kb.new_run_id(),
        "collection_id": label,
        "collection_name": label,
        "roots": roots,
        "depth": args.depth,
        "types": sorted(exts) if exts else [],
        "exclude": args.exclude,
        "write_access": access,
    }
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, sort_keys=True) + "\n")
        for rec in walk(roots, args.depth, exts, args.exclude, args.max_entries):
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    print("inventory -> {}".format(out))


if __name__ == "__main__":
    main()
