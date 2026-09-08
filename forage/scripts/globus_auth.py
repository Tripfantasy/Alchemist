"""Globus auth for the discovery agent.

Two client modes. Confidential is strongly preferred:

  confidential  A service client with its own identity,
                <CLIENT_UUID>@clients.auth.globus.org, which you grant READ-ONLY
                on the guest collection. Globus then refuses writes server-side
                no matter what this code asks for. Runs unattended.

  native        A thick client that acts as YOUR identity, inheriting your write
                access to the collection. The in-process guard in
                scan_endpoint.py becomes the only protection. Supported as a
                fallback; not recommended for this project.

Note on scopes: Globus Transfer has NO read-only scope. It is
transfer.api.globus.org:all or nothing, covering reads and writes together.
Read-only therefore cannot come from scope selection -- it must come from the
collection permission granted to the client identity. See verify_readonly.py.

Secret resolution order (confidential mode), first hit wins:
  1. $GLOBUS_AGENT_CLIENT_SECRET
  2. macOS Keychain, service name "globus_agent_client_secret"
  3. error with setup instructions

Keychain is preferred: an exported env var is inherited by every child process
and tends to end up in shell history and process listings.

Setup
-----
  export GLOBUS_AGENT_CLIENT_ID=<client-uuid>
  security add-generic-password -a "$USER" -s globus_agent_client_secret -w
      # paste the secret at the prompt; -w with no value reads it invisibly
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import globus_sdk
from globus_sdk.scopes import TransferScopes

TOKEN_DIR = Path(os.environ.get("GLOBUS_AGENT_HOME", Path.home() / ".globus_agent"))
TOKEN_FILE = TOKEN_DIR / "tokens.json"
KEYCHAIN_SERVICE = "globus_agent_client_secret"
TRANSFER_RS = globus_sdk.TransferClient.resource_server


# --------------------------------------------------------------------------
# credentials


def client_id() -> str:
    cid = os.environ.get("GLOBUS_AGENT_CLIENT_ID", "").strip()
    if not cid:
        sys.exit(
            "GLOBUS_AGENT_CLIENT_ID is not set.\n"
            "  export GLOBUS_AGENT_CLIENT_ID=<client-uuid>"
        )
    return cid


def client_identity(cid: Optional[str] = None) -> str:
    """The identity a confidential client authenticates as.

    This is the string you grant read-only permission to on the collection.
    """
    return "{}@clients.auth.globus.org".format(cid or client_id())


def _keychain_secret() -> Optional[str]:
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def client_secret(required: bool = True) -> Optional[str]:
    secret = os.environ.get("GLOBUS_AGENT_CLIENT_SECRET", "").strip() or _keychain_secret()
    if secret or not required:
        return secret
    sys.exit(
        "No client secret found.\n\n"
        "Globus generates the secret -- you do not choose it. On your client's\n"
        "page at https://app.globus.org/settings/developers, click\n"
        "'Add Client Secret', give it a label (e.g. globus-agent-2026-08), and\n"
        "copy the generated value. It is shown once.\n\n"
        "Then store it in the macOS Keychain (preferred):\n"
        "  security add-generic-password -a \"$USER\" -s {} -w\n"
        "or, less safely, export GLOBUS_AGENT_CLIENT_SECRET=<secret>".format(
            KEYCHAIN_SERVICE
        )
    )


# --------------------------------------------------------------------------
# scopes


def scopes_for(collection_id: Optional[str] = None, mapped: bool = False) -> List[str]:
    """Base transfer scope, plus data_access only for a MAPPED collection.

    Guest collections do not use data_access; requesting it there fails.
    """
    scope = TransferScopes.make_mutable("all")
    if collection_id and mapped:
        scope.add_dependency(
            globus_sdk.GCSClient.get_gcs_collection_scopes(collection_id).data_access
        )
    return [str(scope)]


# --------------------------------------------------------------------------
# confidential client (recommended)


def get_confidential_client(
    collection_id: Optional[str] = None,
    mapped: bool = False,
) -> globus_sdk.TransferClient:
    cid = client_id()
    app = globus_sdk.ConfidentialAppAuthClient(cid, client_secret())
    authorizer = globus_sdk.ClientCredentialsAuthorizer(
        app, scopes=scopes_for(collection_id, mapped)
    )
    return globus_sdk.TransferClient(authorizer=authorizer)


# --------------------------------------------------------------------------
# native client (fallback)


def _load_tokens() -> dict:
    if not TOKEN_FILE.exists():
        return {}
    try:
        return json.loads(TOKEN_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_tokens(data: dict) -> None:
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data, indent=2))
    TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def get_native_client(
    collection_id: Optional[str] = None,
    mapped: bool = False,
    force_login: bool = False,
) -> globus_sdk.TransferClient:
    app = globus_sdk.NativeAppAuthClient(client_id())
    scopes = scopes_for(collection_id, mapped)

    tokens = {} if force_login else _load_tokens()
    entry = tokens.get(TRANSFER_RS)
    if not entry:
        app.oauth2_start_flow(requested_scopes=scopes, refresh_tokens=True)
        print("\nOpen this URL to authorize the agent:\n")
        print("  " + app.oauth2_get_authorize_url() + "\n")
        code = input("Paste the authorization code here: ").strip()
        if not code:
            sys.exit("No authorization code entered.")
        tokens = app.oauth2_exchange_code_for_tokens(code).by_resource_server
        _save_tokens(tokens)
        entry = tokens[TRANSFER_RS]

    def _persist(response):
        cached = _load_tokens()
        cached.update(response.by_resource_server)
        _save_tokens(cached)

    authorizer = globus_sdk.RefreshTokenAuthorizer(
        entry["refresh_token"], app,
        access_token=entry.get("access_token"),
        expires_at=entry.get("expires_at_seconds"),
        on_refresh=_persist,
    )
    return globus_sdk.TransferClient(authorizer=authorizer)


# --------------------------------------------------------------------------
# entry point


def get_transfer_client(
    collection_id: Optional[str] = None,
    mode: str = "auto",
    mapped: bool = False,
) -> globus_sdk.TransferClient:
    """Return an authenticated TransferClient.

    mode: "confidential" | "native" | "auto" (confidential if a secret exists)
    """
    if mode == "auto":
        mode = "confidential" if client_secret(required=False) else "native"
    if mode == "confidential":
        return get_confidential_client(collection_id, mapped)
    if mode == "native":
        print("WARNING: native mode acts as your own identity and inherits your "
              "write access.\n         Prefer a confidential client granted "
              "read-only on the collection.")
        return get_native_client(collection_id, mapped)
    raise ValueError("unknown auth mode {!r}".format(mode))


def ensure_consent(
    transfer_client: globus_sdk.TransferClient,
    collection_id: str,
    path: str = "/",
    mode: str = "auto",
) -> globus_sdk.TransferClient:
    """Probe the collection and surface actionable errors early.

    A long walk should not fail on its thousandth listing for a reason that was
    knowable on the first.
    """
    try:
        transfer_client.operation_ls(collection_id, path=path, limit=1)
        return transfer_client
    except globus_sdk.TransferAPIError as err:
        if err.info.consent_required:
            print("Collection requires data_access consent (mapped collection); "
                  "re-authorizing.")
            return get_transfer_client(collection_id, mode=mode, mapped=True)
        if err.http_status in (403, 401):
            sys.exit(
                "Access denied listing {} on {}.\n\n"
                "If this is the confidential client, it needs a read permission "
                "on the guest collection:\n"
                "  globus endpoint permission create {}:{} \\\n"
                "      --identity {} --permissions r\n".format(
                    path, collection_id, collection_id, path, client_identity()
                )
            )
        raise


if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else None
    probe = sys.argv[2] if len(sys.argv) > 2 else "/"
    print("client id       : {}".format(client_id()))
    print("client identity : {}".format(client_identity()))
    print("secret found    : {}".format(bool(client_secret(required=False))))
    tc = get_transfer_client(cid)
    if not cid:
        print("authenticated (no collection given)")
        sys.exit(0)
    tc = ensure_consent(tc, cid, probe)
    info = tc.get_endpoint(cid)
    print("collection      : {} [{}]".format(info["display_name"], info["entity_type"]))
    for item in tc.operation_ls(cid, path=probe, limit=10):
        print("  {:4} {}".format(item["type"], item["name"]))
