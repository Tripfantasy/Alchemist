#!/usr/bin/env python3
"""First-time configuration for forage and sigil. Driven by /setup.

    python3 .claude/lib/setup.py status [forage|sigil]   # what is configured
    python3 .claude/lib/setup.py backend globus          # forage reads Globus
    python3 .claude/lib/setup.py backend local --root /mnt/lab [--root ...] [--label NAME]
    python3 .claude/lib/setup.py venv forage|sigil       # create the agent's venv
    python3 .claude/lib/setup.py lab < lab.json          # sigil's lab details (merge)

Rules this script keeps, so the command file does not have to trust itself:

- It NEVER prints a UUID or the client secret. Globus settings are reported by
  variable name and status only; the Keychain secret by presence only.
- It never touches the collection, scans nothing, and never writes Globus
  settings. The researcher puts UUIDs in forage/.claude/settings.json and the
  secret in the Keychain themselves, outside the chat.
- `backend` only writes the backend keys of forage/resources/site.json and
  keeps every other key. Choosing 'globus' leaves the Globus setup as it was.
- `lab` merges name/description/pi into sigil/resources/lab.json and keeps
  everything sigil has added (publications, theme groups, term merges).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FORAGE = ROOT / "forage"
SIGIL = ROOT / "sigil"
SITE = FORAGE / "resources" / "site.json"
SITE_EXAMPLE = FORAGE / "resources" / "site.example.json"
FORAGE_SETTINGS = FORAGE / ".claude" / "settings.json"
LAB = SIGIL / "resources" / "lab.json"
GLOBUS_VARS = ("GLOBUS_AGENT_CLIENT_ID", "GLOBUS_AGENT_COLLECTION_ID")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
KEYCHAIN_SERVICE = "globus_agent_client_secret"


def _json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        sys.exit(f"FAIL  {path.relative_to(ROOT)} is not valid JSON: {exc}")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _line(state: str, what: str, note: str = "") -> None:
    print(f"  {state:<8} {what}" + (f"  -- {note}" if note else ""))


# --- status -----------------------------------------------------------------

def status_forage() -> bool:
    print("forage")
    ok = True
    venv = (FORAGE / ".venv" / "bin" / "python").exists()
    _line("ok" if venv else "MISSING", "venv", "" if venv else "setup.py venv forage")
    ok &= venv

    site = _json(SITE)
    if not site:
        _line("MISSING", "resources/site.json", "choose a backend: setup.py backend globus|local")
        return False
    backend = site.get("backend", "globus")
    _line("ok", "backend: " + backend + ("" if "backend" in site else " (default)"))

    if backend == "local":
        roots = site.get("local_roots") or []
        if not roots:
            _line("MISSING", "local_roots", "setup.py backend local --root <dir>")
            return False
        for r in roots:
            p = os.path.abspath(os.path.expanduser(r))
            if not os.path.isdir(p):
                _line("MISSING", "root " + r, "not a directory on this machine")
                ok = False
                continue
            ro = bool(os.statvfs(p).f_flag & os.ST_RDONLY) or not os.access(p, os.W_OK)
            _line("ok" if ro else "WRITABLE", "root " + r,
                  "" if ro else "scans will be refused; mount it read-only (see forage/LOCAL.md)")
        _line("ok", "local_label: " + (site.get("local_label") or "local:<hostname> (default)"))
        return ok

    env = _json(FORAGE_SETTINGS).get("env", {})
    for var in GLOBUS_VARS:
        val = env.get(var, "")
        state = "ok" if UUID.match(val) else "MISSING" if not val or "<" in val else "INVALID"
        _line(state, var + " in forage/.claude/settings.json",
              "" if state == "ok" else "copy settings.json.example and fill it in yourself")
        ok &= state == "ok"
    secret = _keychain_has_secret()
    _line({True: "ok", False: "MISSING", None: "UNKNOWN"}[secret],
          "client secret in Keychain (" + KEYCHAIN_SERVICE + ")",
          "" if secret else "add it yourself, in a terminal (see /setup)")
    ok &= bool(secret)
    if ok:
        root_env = _json(ROOT / ".claude" / "settings.json").get("env", {})
        synced = all(root_env.get(v) == env.get(v) for v in GLOBUS_VARS)
        _line("ok" if synced else "STALE", "root .claude/settings.json mirror",
              "" if synced else "python3 .claude/lib/agent_env.py sync")
        ok &= synced
    return ok


def _keychain_has_secret():
    if not shutil.which("security"):
        return None  # not macOS; cannot tell
    r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE],
                       capture_output=True, text=True)  # no -w: the secret is never read
    return r.returncode == 0


def status_sigil() -> bool:
    print("sigil")
    lab = _json(LAB)
    ok = (SIGIL / ".venv" / "bin" / "python").exists()  # render_report needs it
    _line("ok" if ok else "MISSING", "venv", "" if ok else "setup.py venv sigil")
    for key in ("name", "description"):
        has = bool(str(lab.get(key, "")).strip())
        _line("ok" if has else "MISSING", "lab " + key)
        ok &= has
    pi = lab.get("pi") or {}
    has_pi = bool(pi.get("name"))
    _line("ok" if has_pi else "MISSING", "PI name / affiliations")
    ok &= has_pi
    _line("ok" if pi.get("orcid") else "optional", "PI ORCID")
    snap = (FORAGE / "knowledge" / "snapshot.json").exists()
    _line("ok" if snap else "later", "forage snapshot",
          "" if snap else "sigil needs one forage scan first")
    return ok


def cmd_status(which: list[str]) -> int:
    which = which or ["forage", "sigil"]
    results = {}
    for agent in which:
        if agent not in ("forage", "sigil"):
            sys.exit(f"FAIL  unknown agent {agent!r}")
        results[agent] = (status_forage if agent == "forage" else status_sigil)()
    print()
    for agent, ok in results.items():
        print(f"{'CONFIGURED' if ok else 'NEEDS SETUP':<12} {agent}")
    return 0 if all(results.values()) else 1


# --- writers ----------------------------------------------------------------

def cmd_backend(args: list[str]) -> int:
    if not args or args[0] not in ("globus", "local"):
        sys.exit("usage: setup.py backend globus | local --root DIR [--root DIR] [--label NAME]")
    choice, rest = args[0], args[1:]
    roots, label = [], None
    while rest:
        flag = rest.pop(0)
        if flag == "--root" and rest:
            roots.append(rest.pop(0))
        elif flag == "--label" and rest:
            label = rest.pop(0)
        else:
            sys.exit(f"FAIL  unexpected argument {flag!r}")
    site = _json(SITE) or _json(SITE_EXAMPLE)
    site["backend"] = choice
    if choice == "local":
        if not roots:
            sys.exit("FAIL  the local backend needs at least one --root")
        clean = []
        for r in roots:
            p = os.path.abspath(os.path.expanduser(r))
            if not os.path.isdir(p):
                sys.exit(f"FAIL  not a directory: {r}")
            if p == "/" or p == os.path.expanduser("~"):
                sys.exit(f"FAIL  {p} is too broad for a root; name the data directory")
            clean.append(p.rstrip("/") + "/")
        site["local_roots"] = clean
        if label:
            site["local_label"] = label
    _write(SITE, site)
    print(f"written: forage/resources/site.json  (backend: {choice}; other keys kept)")
    return 0


def cmd_venv(args: list[str]) -> int:
    if not args or args[0] not in ("forage", "sigil"):
        sys.exit("usage: setup.py venv forage|sigil")
    agent = ROOT / args[0]
    py = agent / ".venv" / "bin" / "python"
    if not py.exists():
        subprocess.run([sys.executable, "-m", "venv", str(agent / ".venv")], check=True)
    req = agent / "requirements.txt"
    if req.exists():
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(req)], check=True)
    print(f"ok: {args[0]}/.venv")
    return 0


def cmd_lab() -> int:
    try:
        new = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.exit(f"FAIL  lab details are not valid JSON: {exc}")
    allowed = {"name", "description", "pi"}
    extra = set(new) - allowed
    if extra:
        sys.exit(f"FAIL  setup writes only {sorted(allowed)}; got {sorted(extra)}")
    lab = _json(LAB)
    lab.update({k: v for k, v in new.items() if v not in (None, "", {})})
    _write(LAB, lab)
    print("written: sigil/resources/lab.json  (name, description, pi; other keys kept)")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    if cmd == "status":
        return cmd_status(rest)
    if cmd == "backend":
        return cmd_backend(rest)
    if cmd == "venv":
        return cmd_venv(rest)
    if cmd == "lab":
        return cmd_lab()
    sys.exit(__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
