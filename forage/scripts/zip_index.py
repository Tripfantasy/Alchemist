"""List what is inside .zip archives on the collection, without downloading them.

Globus Transfer can list directories but never looks inside a file, so a 1 TB
archive is a single opaque entry in every scan. A zip, though, ends with a
central directory: a table of contents giving every member's name, size and
date. This script fetches only that tail over the collection's HTTPS server,
using HTTP byte-range requests, and writes the members out as an ordinary
inventory -- so build_index.py and search.py work on them unchanged.

Cost: a few HTTPS requests and typically a few MB per archive, regardless of
the archive's size. Member DATA is never requested.

Read-only, and why this does not breach it
------------------------------------------
CLAUDE.md: "Only read the files in the globus directories, NEVER edit, move, or
copy files." This reads part of a file -- its index -- into memory and keeps
only the listing. Nothing is transferred, and no fetched bytes are ever written
to disk. Three guards:

1. Collection permission. The client holds `r`, so the HTTPS server rejects any
   write regardless of what this code sends. This is the guarantee.
2. ReadOnlyHTTPS issues GET and HEAD only; any other method raises.
3. --max-index-mb caps the total bytes read per archive (default 256). A bug
   that started reading member data would hit the cap long before it amounted
   to a download.

Output paths use `<archive>!/<member>` (the jar-URL convention), so every
member is traceable to the archive that holds it and cannot be mistaken for a
file that exists on the collection in its own right.

Usage
-----
  # 1. Detect (local, no network): which archives are in an inventory's scope?
  ./.venv/bin/python scripts/zip_index.py --find knowledge/inventory.jsonl \
      --folder /core_archives/

  # 2. After the researcher agrees, list the contents of the ones they picked
  ./.venv/bin/python scripts/zip_index.py "$GLOBUS_AGENT_COLLECTION_ID" \
      --zip /core_archives/secondary_part1.zip \
      --zip /core_archives/secondary_part2.zip \
      --out knowledge/inventory_zip_core.jsonl

  Then index it like any scan:
  ./.venv/bin/python scripts/build_index.py --inventory knowledge/inventory_zip_core.jsonl

Confidential-client mode only: the HTTPS token comes from client credentials.
"""

import argparse
import io
import json
import sys
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterator, List

import globus_sdk
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402
from globus_auth import client_id, client_secret, ensure_consent, get_transfer_client  # noqa: E402
from scan_endpoint import ReadOnlyTransferClient  # noqa: E402

SEP = "!/"


class ReadCapExceeded(RuntimeError):
    pass


class ReadOnlyHTTPS:
    """GET/HEAD-only session against the collection's HTTPS server."""

    ALLOWED = ("GET", "HEAD")

    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/")
        self._s = requests.Session()
        self._s.headers["Authorization"] = "Bearer " + token

    def url(self, path: str) -> str:
        return self.base + urllib.parse.quote(path)

    def request(self, method: str, path: str, **kw) -> requests.Response:
        if method.upper() not in self.ALLOWED:
            raise PermissionError(
                "{} is blocked: this agent is read-only on Globus collections "
                "(see CLAUDE.md).".format(method))
        r = self._s.request(method, self.url(path), timeout=120, **kw)
        r.raise_for_status()
        return r


class RangeFile(io.RawIOBase):
    """Seekable, read-only file object backed by HTTP Range requests.

    zipfile only needs seek/tell/read. Opening a ZipFile reads the end-of-
    central-directory record, the ZIP64 locator if any, and the central
    directory itself -- never member data.
    """

    def __init__(self, http: ReadOnlyHTTPS, path: str, cap_bytes: int):
        self.http, self.path, self.cap = http, path, cap_bytes
        head = http.request("HEAD", path, allow_redirects=True)
        if head.headers.get("Accept-Ranges", "").lower() != "bytes":
            raise RuntimeError("server does not support byte ranges for " + path)
        self.size = int(head.headers["Content-Length"])
        self.pos = 0
        self.bytes_read = 0
        self.requests = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        base = {0: 0, 1: self.pos, 2: self.size}[whence]
        self.pos = max(0, min(self.size, base + offset))
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        end = self.size if n is None or n < 0 else min(self.size, self.pos + n)
        if end <= self.pos:
            return b""
        want = end - self.pos
        if self.bytes_read + want > self.cap:
            raise ReadCapExceeded(
                "reading {:,} more bytes would pass the {:,}-byte cap for {} -- "
                "raise --max-index-mb only if the central directory is genuinely "
                "that large".format(want, self.cap, self.path))
        r = self.http.request(
            "GET", self.path,
            headers={"Range": "bytes={}-{}".format(self.pos, end - 1)},
            allow_redirects=True)
        if r.status_code != 206:
            # A 200 here means the server ignored Range and is sending the
            # whole archive. Stop before consuming it.
            r.close()
            raise RuntimeError("expected 206 Partial Content, got {}".format(r.status_code))
        data = r.content
        self.requests += 1
        self.bytes_read += len(data)
        self.pos += len(data)
        return data

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def https_client(collection_id: str) -> ReadOnlyHTTPS:
    tc = ReadOnlyTransferClient(
        ensure_consent(get_transfer_client(collection_id, mode="confidential"),
                       collection_id, "/", mode="confidential"))
    server = tc.get_endpoint(collection_id).get("https_server")
    if not server:
        sys.exit("This collection exposes no HTTPS server; archive listing is "
                 "not possible without downloading.")
    app = globus_sdk.ConfidentialAppAuthClient(client_id(), client_secret())
    scope = "https://auth.globus.org/scopes/{}/https".format(collection_id)
    tokens = app.oauth2_client_credentials_tokens(requested_scopes=scope)
    return ReadOnlyHTTPS(server, tokens.by_resource_server[collection_id]["access_token"])


def members(http: ReadOnlyHTTPS, zip_path: str, cap_bytes: int) -> Iterator[dict]:
    rf = RangeFile(http, zip_path, cap_bytes)
    try:
        zf = zipfile.ZipFile(io.BufferedReader(rf, buffer_size=1 << 16))
    except (zipfile.BadZipFile, ReadCapExceeded, RuntimeError,
            requests.RequestException) as err:
        yield {"kind": "error", "path": zip_path,
               "code": type(err).__name__, "message": str(err)[:300]}
        return

    base_depth = zip_path.count("/")
    n_files = n_dirs = 0
    for info in zf.infolist():
        full = zip_path + SEP + info.filename
        depth = base_depth + info.filename.rstrip("/").count("/")
        if info.is_dir():
            n_dirs += 1
            yield {"kind": "dir", "path": full, "name": info.filename.rstrip("/").split("/")[-1] + "/",
                   "depth": depth, "archive": zip_path}
            continue
        n_files += 1
        name = info.filename.split("/")[-1]
        try:
            mtime = datetime(*info.date_time).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            mtime = ""
        yield {
            "kind": "file",
            "path": full,
            "name": name,
            "ext": kb._ext(name),
            "size": info.file_size,
            "compressed_size": info.compress_size,
            "last_modified": mtime,
            "depth": depth,
            "archive": zip_path,
            "anchors": kb.extract_anchors(full),
        }
    print("zip: {} | {:,} files, {:,} dirs | read {:,} bytes in {} request(s) "
          "of a {:,}-byte archive".format(zip_path, n_files, n_dirs, rf.bytes_read,
                                          rf.requests, rf.size), flush=True)


def find_archives(inventory: str, folders: List[str]) -> None:
    """Local only: list .zip archives an inventory holds, so the researcher can
    be asked whether to look inside them. Makes no network calls."""
    found = []
    for rec in kb.iter_records(Path(inventory)):
        if rec.get("kind") != "file" or SEP in rec.get("path", ""):
            continue  # skip members of archives already opened
        p = rec["path"]
        if p.lower().endswith(".zip") and (not folders or any(p.startswith(f) for f in folders)):
            found.append(rec)
    if not found:
        print("no .zip archives in scope")
        return
    found.sort(key=lambda r: -(r.get("size") or 0))
    total = sum(r.get("size") or 0 for r in found)
    print("{} .zip archive(s) in scope, {:,.1f} GB total -- contents invisible to "
          "search until listed:".format(len(found), total / 1e9))
    for r in found:
        print("  {:>9,.1f} GB  {}  {}".format((r.get("size") or 0) / 1e9,
                                             str(r.get("last_modified", ""))[:10], r["path"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("collection", nargs="?",
                    help="collection UUID (pass $GLOBUS_AGENT_COLLECTION_ID); not needed with --find")
    ap.add_argument("--find", metavar="INVENTORY",
                    help="local only: list the .zip archives in an inventory and exit")
    ap.add_argument("--folder", action="append", default=[],
                    help="with --find: only archives under this prefix; repeatable")
    ap.add_argument("--zip", action="append", default=[],
                    help="path of a .zip on the collection; repeatable")
    ap.add_argument("--max-index-mb", type=int, default=256,
                    help="max bytes read per archive, in MB (default 256)")
    ap.add_argument("--out", help="inventory JSONL to write")
    args = ap.parse_args()

    if args.find:
        find_archives(args.find, args.folder)
        return
    if not (args.collection and args.zip and args.out):
        ap.error("listing archives needs: collection, --zip (one or more), --out")

    zips: List[str] = args.zip
    bad = [z for z in zips if not z.lower().endswith(".zip")]
    if bad:
        sys.exit("not .zip archives: {}".format(", ".join(bad)))

    http = https_client(args.collection)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "kind": "scan_meta",
        "source": "zip_central_directory",
        "ts": kb.utc_now(),
        "run_id": kb.new_run_id(),
        "collection_id": args.collection,
        "roots": zips,
        "depth": None,
        "types": [],
        "exclude": [],
    }
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, sort_keys=True) + "\n")
        for z in zips:
            for rec in members(http, z, args.max_index_mb << 20):
                if rec["kind"] == "error":
                    print("zip: {} UNREADABLE -- {}: {}".format(
                        z, rec["code"], rec["message"]), flush=True)
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    print("inventory -> {}".format(out))


if __name__ == "__main__":
    main()
