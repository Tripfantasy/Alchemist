#!/usr/bin/env python3
"""Mirror each agent's .claude/settings.json env into the root settings.json.

WHY THIS EXISTS
---------------
Claude Code reads `.claude/settings.json` from the directory the session was
started in. A session started at the repo root therefore never sees
`forage/.claude/settings.json`, so GLOBUS_AGENT_CLIENT_ID and
GLOBUS_AGENT_COLLECTION_ID are unset and every scan fails at auth.

`cd forage` does not fix it: the harness keeps the working directory between
Bash calls but NOT the shell environment, so an `export` in one call is gone by
the next. The env has to come from settings.json, which means the root needs its
own copy.

So the root gets a generated `.claude/settings.json` holding the union of the
agents' env blocks. The agents' own files stay the source of truth; this only
copies. Re-run `sync` whenever an agent's UUIDs change.

UUIDs ARE NEVER PRINTED. Both subcommands report set / unset / mismatch by name
only. Writing an infrastructure UUID to a terminal is how it ends up pasted into
a report, and forage/CLAUDE.md forbids exactly that.

A sync may or may not take effect in the session that ran it -- harnesses differ
in whether they re-read settings.json per command or only at startup. Do not
assume either; run `check` and believe it.

    python3 .claude/lib/agent_env.py check forage   # is this session usable?
    python3 .claude/lib/agent_env.py sync           # refresh root settings.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ("distill", "brew", "forage")
ROOT_SETTINGS = ROOT / ".claude" / "settings.json"


def agent_env(agent: str) -> dict[str, str]:
    """The env block from an agent's settings.json, or {} if it has none."""
    path = ROOT / agent / ".claude" / "settings.json"
    if not path.exists():
        return {}
    try:
        return dict(json.loads(path.read_text()).get("env", {}))
    except json.JSONDecodeError as exc:
        sys.exit(f"FAIL  {path.relative_to(ROOT)} is not valid JSON: {exc}")


def collect() -> dict[str, str]:
    """Union of every agent's env. A same-key conflict is fatal, not resolved.

    One root settings.json cannot hold two values for one variable. Picking a
    winner would leave one agent silently pointed at the other's collection, so
    this stops and makes a person decide.
    """
    merged: dict[str, str] = {}
    owner: dict[str, str] = {}
    for agent in AGENTS:
        for key, value in agent_env(agent).items():
            if key in merged and merged[key] != value:
                sys.exit(
                    f"FAIL  {agent} and {owner[key]} both set {key}, to different\n"
                    f"      values. The root can only carry one. Reconcile them in\n"
                    f"      the agents' own settings.json files first."
                )
            merged[key] = value
            owner.setdefault(key, agent)
    return merged


def cmd_sync() -> int:
    merged = collect()
    if not merged:
        print("nothing to sync -- no agent defines an env block")
        return 0

    # Preserve anything already in the root file; only the env block is ours.
    existing: dict = {}
    if ROOT_SETTINGS.exists():
        try:
            existing = json.loads(ROOT_SETTINGS.read_text())
        except json.JSONDecodeError as exc:
            sys.exit(f"FAIL  existing {ROOT_SETTINGS.name} is not valid JSON: {exc}")

    was = existing.get("env", {})
    existing["env"] = merged
    ROOT_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    ROOT_SETTINGS.write_text(json.dumps(existing, indent=2) + "\n")

    verb = "unchanged" if was == merged else "written"
    print(f"{verb}: .claude/settings.json   ({len(merged)} vars: {', '.join(sorted(merged))})")
    if was != merged:
        print(
            "\nNow run:  python3 .claude/lib/agent_env.py check <agent>\n"
            "Some harnesses re-read settings.json per command and will pick this up\n"
            "immediately; others read it only at session start. The check says which."
        )
    return 0


def cmd_check(agent: str) -> int:
    if agent not in AGENTS:
        sys.exit(f"FAIL  unknown agent {agent!r} (expected one of: {', '.join(AGENTS)})")

    wanted = agent_env(agent)
    if not wanted:
        print(f"OK    {agent} needs no environment")
        return 0

    missing = [k for k in wanted if not os.environ.get(k)]
    mismatch = [k for k in wanted if os.environ.get(k) and os.environ[k] != wanted[k]]

    for key in sorted(wanted):
        state = "MISSING" if key in missing else "STALE" if key in mismatch else "ok"
        print(f"  {state:<8} {key}")

    if not missing and not mismatch:
        print(f"OK    this session carries {agent}'s environment")
        return 0

    print(
        f"\nFAIL  this session cannot run {agent}.\n"
        f"      Fix:  python3 .claude/lib/agent_env.py sync\n"
        f"      then restart the session -- settings.json is read only at startup."
    )
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] not in {"check", "sync"}:
        sys.exit(__doc__)
    if args[0] == "sync":
        return cmd_sync()
    if len(args) < 2:
        sys.exit("FAIL  check needs an agent name")
    return cmd_check(args[1])


if __name__ == "__main__":
    raise SystemExit(main())
