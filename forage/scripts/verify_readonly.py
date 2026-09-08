"""Verify the agent cannot write to a Globus collection.

Checks four things, none of which modify anything:

  1. the in-process guard blocks every mutating TransferClient method
  2. the token authenticates and can list (reads work)
  3. the ACL granted to the client identity is r, not rw
  4. the client is not itself an access manager (it cannot re-grant to itself)

Why this does not test by attempting a write
--------------------------------------------
The obvious test is to call operation_mkdir and assert it fails. That test
creates a directory on your collection whenever it fails -- precisely the
outcome the agent promises can never happen. A check for "nothing is ever
created" must not create something in its failure mode. So this reads the
permission list instead, which answers the same question with no side effects.

Reading ACLs requires an access-manager role on the collection, which the
read-only client deliberately does NOT have. So step 3 usually runs as you:

  # as the collection administrator (your own login)
  globus endpoint permission list <COLLECTION_UUID>

  # as the agent's client, to confirm it is correctly powerless
  python3 scripts/verify_readonly.py <COLLECTION_UUID>

Usage
-----
  python3 scripts/verify_readonly.py <COLLECTION_UUID> [--path /]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import globus_sdk  # noqa: E402

import globus_auth  # noqa: E402
from scan_endpoint import FORBIDDEN, ReadOnlyTransferClient, ReadOnlyViolation  # noqa: E402

PASS = "  PASS  "
FAIL = "  FAIL  "
INFO = "  ..    "
WARN = "  WARN  "


class _Recorder:
    """Stand-in that records any call reaching it, so a leak is visible."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _call(*a, **k):
            self.calls.append(name)
            return "REACHED-THE-NETWORK"
        return _call


def check_guard() -> bool:
    print("\n[1] in-process guard")
    recorder = _Recorder()
    guarded = ReadOnlyTransferClient(recorder)
    leaked = []
    for name in FORBIDDEN:
        try:
            getattr(guarded, name)
            leaked.append(name)
        except ReadOnlyViolation:
            pass
    if leaked:
        print(FAIL + "these mutating methods were NOT blocked: " + ", ".join(leaked))
        return False
    print(PASS + "all {} mutating methods blocked".format(len(FORBIDDEN)))
    if recorder.calls:
        print(FAIL + "calls reached the client: " + ", ".join(recorder.calls))
        return False
    print(PASS + "no mutating call reached the underlying client")
    return True


def check_read(client, collection_id: str, path: str):
    print("\n[2] authentication and read access")
    try:
        info = client.get_endpoint(collection_id)
    except globus_sdk.TransferAPIError as err:
        print(FAIL + "cannot read collection: {} {}".format(err.http_status, err.code))
        return None
    print(PASS + "authenticated as {}".format(globus_auth.client_identity()))
    print(INFO + "collection: {} [{}]".format(
        info["display_name"], info.get("entity_type", "?")))

    if info.get("entity_type") == "GCSv5_mapped_collection":
        print(WARN + "this is a MAPPED collection -- it authenticates as a local "
                     "POSIX account,\n          so ACLs may not govern. Prefer a "
                     "read-only guest collection on top.")

    try:
        entries = list(client.operation_ls(collection_id, path=path, limit=5))
    except globus_sdk.TransferAPIError as err:
        print(FAIL + "cannot list {}: {} {}".format(path, err.http_status, err.code))
        return info
    print(PASS + "listed {} ({} entries visible)".format(path, len(entries)))
    return info


def check_acls(client, collection_id: str) -> None:
    print("\n[3] permissions granted on the collection")
    identity = globus_auth.client_identity()
    try:
        rules = list(client.endpoint_acl_list(collection_id))
    except globus_sdk.TransferAPIError as err:
        if err.http_status in (401, 403):
            print(PASS + "client cannot read ACLs -- it is not an access manager,")
            print("          so it cannot grant itself write access.")
            print(INFO + "verify the grant as the collection admin:")
            print("          globus endpoint permission list {}".format(collection_id))
            return
        print(WARN + "could not list ACLs: {} {}".format(err.http_status, err.code))
        return

    print(WARN + "this client CAN read ACLs, so it holds an access-manager role.")
    print("          A read-only agent should not. Consider removing that role.")

    mine = [r for r in rules
            if identity in (r.get("principal", ""), r.get("principal_email", ""))]
    if not mine:
        print(INFO + "no ACL found for {} (access may come from a group)".format(identity))
    for rule in mine:
        perms = rule.get("permissions", "")
        marker = PASS if perms == "r" else FAIL
        print(marker + "{} on {} -> permissions '{}'".format(
            identity, rule.get("path", "/"), perms))
        if perms != "r":
            print("          Revoke and re-grant with --permissions r")


def check_write_capability_hint(collection_id: str) -> None:
    print("\n[4] how to confirm the grant, as the collection admin")
    print(INFO + "globus endpoint permission list {}".format(collection_id))
    print("          Expect exactly one rule for")
    print("            {}".format(globus_auth.client_identity()))
    print("          with permissions 'r'. Anything showing 'rw' must be revoked.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("collection", help="Globus collection UUID")
    ap.add_argument("--path", default="/", help="path to probe with a listing")
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "confidential", "native"])
    args = ap.parse_args()

    print("=" * 66)
    print("Read-only verification for {}".format(args.collection))
    print("=" * 66)

    ok = check_guard()

    raw = globus_auth.get_transfer_client(args.collection, mode=args.mode)
    client = ReadOnlyTransferClient(raw)

    info = check_read(client, args.collection, args.path)
    if info is not None:
        check_acls(client, args.collection)
    check_write_capability_hint(args.collection)

    print("\n" + "=" * 66)
    if ok and info is not None:
        print("Guard verified and reads work. Confirm the ACL shows 'r' as admin.")
    else:
        print("Verification INCOMPLETE -- resolve the failures above before scanning.")
        sys.exit(1)


if __name__ == "__main__":
    main()
