#!/usr/bin/env python3
"""Opt-in bias reporting across the three Alchemist agents.

Records what influenced a run OTHER than the request and that run's clarifying
answers -- the standing user profile, prior outputs, the knowledge store, the
vocabulary, earlier turns. See bias/README.md for what counts and why.

Deliberately dependency-free and stdlib-only: every agent has its own venv, and
this is the one thing all three share. Run it with any python3.

  python3 bias/report.py status
  python3 bias/report.py enable | disable
  python3 bias/report.py append --file run.json
  python3 bias/report.py summarize [--agent distill] [--last 20]
"""

import argparse
import json
import sys
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent

# Two files, on purpose. config.json is TRACKED and ships `enabled: false` --
# that default is part of the agent, so a fresh clone starts opted out. Every
# runtime answer goes to config.local.json, which is GITIGNORED, so answering
# the bias question never dirties a tracked file and a clone is never tainted
# by someone else's session. Local wins where both set a key.
CONFIG = HERE / "config.json"
CONFIG_LOCAL = HERE / "config.local.json"
LOG = HERE / "log.jsonl"

AGENTS = ("distill", "brew", "forage")

# Kept open on purpose: an unrecognised source is recorded with a warning
# rather than rejected. A refused record is a record that does not exist, and
# the whole point is to capture influences nobody anticipated.
KNOWN_SOURCES = {
    "claude_md_profile": "the About Me / project profile",
    "prior_output": "reports already in the agent's output/",
    "local_file": "a file read off disk without an intake answer authorizing it",
    "knowledge_store": "forage's query log or association store",
    "vocab": "vocab.json, seeded from one lab's metadata",
    "method_gaps": "brew's accumulated per-lab omission notes",
    "conversation_history": "earlier turns, when this request is independent",
    "memory": "anything recalled from a previous session",
}


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        # Never let a malformed config silently read as "enabled".
        print("bias: {} is unreadable ({}) -- ignoring it, which means "
              "DISABLED unless the other file says otherwise"
              .format(path.name, err), file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print("bias: {} is not an object -- ignoring it"
              .format(path.name), file=sys.stderr)
        return {}
    return data


def load_config() -> Dict:
    """Tracked defaults, overlaid with local state. Absent both, opted out."""
    cfg = {"enabled": False}
    cfg.update(_read_json(CONFIG))
    cfg.update(_read_json(CONFIG_LOCAL))
    return cfg


def save_config(cfg: Dict) -> None:
    """Write ONLY the local override. config.json is tracked and must keep
    shipping `enabled: false`; a runtime answer that edited it would put one
    person's session into everyone else's clone."""
    shipped = _read_json(CONFIG)
    local = {k: v for k, v in cfg.items()
             # _comment is documentation and lives in the tracked file; keys
             # that merely echo the shipped value need not be restated.
             if k != "_comment" and shipped.get(k) != v}
    local["_comment"] = ("Local bias-reporting state, gitignored. The tracked "
                         "default lives in config.json; this file overrides "
                         "it for this machine only. Safe to delete -- doing so "
                         "reverts to the shipped default.")
    CONFIG_LOCAL.write_text(json.dumps(local, indent=2) + "\n",
                            encoding="utf-8")


def is_enabled() -> bool:
    return bool(load_config().get("enabled"))


# --------------------------------------------------------------------------
# append
# --------------------------------------------------------------------------

def validate(rec: Dict) -> List[str]:
    problems = []
    agent = rec.get("agent")
    if agent not in AGENTS:
        problems.append("agent must be one of {}, got {!r}"
                        .format(", ".join(AGENTS), agent))
    if not rec.get("query"):
        problems.append("query is required -- the request this run answered")
    if "influences" not in rec:
        problems.append("influences is required (use [] for none -- an empty "
                        "list is a meaningful record, a missing key is not)")

    for i, inf in enumerate(rec.get("influences") or []):
        for field in ("source", "supplied", "effect"):
            if not inf.get(field):
                problems.append("influences[{}].{} is required".format(i, field))
        src = inf.get("source")
        if src and src not in KNOWN_SOURCES:
            print("bias: note -- unrecognised source {!r}, recorded anyway"
                  .format(src), file=sys.stderr)

    # unasked_fills went unvalidated until 2026-09-10, and a run keyed its
    # entries on "what" instead of "fact". It appended cleanly, reported
    # "2 unasked fill(s)", and summarized as "2x None" -- the content was in
    # the log but the highest-signal line of the cross-run view was blank.
    # summarize reads `fact` and nothing else, so `fact` is the hard error.
    for i, fill in enumerate(rec.get("unasked_fills") or []):
        if not isinstance(fill, dict):
            problems.append("unasked_fills[{}] must be an object with a "
                            "'fact' key, got {}"
                            .format(i, type(fill).__name__))
            continue
        if not fill.get("fact"):
            near = [k for k in ("what", "assumption", "item", "name", "supplied")
                    if fill.get(k)]
            problems.append(
                "unasked_fills[{}].fact is required{} -- summarize counts "
                "fills by 'fact' and renders anything else as None"
                .format(i, " (rename {!r})".format(near[0]) if near else ""))
        for field in ("basis", "effect"):
            if not fill.get(field):
                print("bias: note -- unasked_fills[{}] has no {!r}, recorded "
                      "anyway (summarize does not read it, but a reader of "
                      "the log will look for it)".format(i, field),
                      file=sys.stderr)
    return problems


def cmd_append(args) -> int:
    raw = (Path(args.file).read_text(encoding="utf-8") if args.file
           else sys.stdin.read())
    rec = json.loads(raw)

    problems = validate(rec)
    if problems:
        for p in problems:
            print("bias: {}".format(p), file=sys.stderr)
        return 2

    if not is_enabled():
        # Refusing to write when disabled is the point of an opt-in: the log
        # must never accumulate without the user having turned it on.
        print("bias: reporting is DISABLED -- nothing written. "
              "Enable with: python3 bias/report.py enable", file=sys.stderr)
        return 1

    rec.setdefault("run_id", uuid.uuid4().hex[:12])
    rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    rec.setdefault("influences", [])
    rec.setdefault("unasked_fills", [])
    rec.setdefault("slots", [])

    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")

    n_inf = len(rec["influences"])
    n_fill = len(rec["unasked_fills"])
    print("bias: logged {} [{}] -- {} influence(s), {} unasked fill(s)"
          .format(rec["run_id"], rec["agent"], n_inf, n_fill))
    if n_fill:
        print("      unasked fills are candidate intake slots -- review them")
    return 0


# --------------------------------------------------------------------------
# summarize
# --------------------------------------------------------------------------

def read_log() -> List[Dict]:
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def cmd_summarize(args) -> int:
    runs = read_log()
    if args.agent:
        runs = [r for r in runs if r.get("agent") == args.agent]
    if args.last:
        runs = runs[-args.last:]

    if not runs:
        print("bias: no runs logged"
              + (" for {}".format(args.agent) if args.agent else ""))
        return 0

    print("\nbias report -- {} run(s), {} .. {}".format(
        len(runs), runs[0].get("ts", "?"), runs[-1].get("ts", "?")))

    by_agent = Counter(r.get("agent") for r in runs)
    print("\n  runs by agent: {}".format(
        ", ".join("{} {}".format(v, k) for k, v in by_agent.most_common())))

    clean = sum(1 for r in runs if not r.get("influences"))
    print("  runs with no influence beyond the request: {}/{}"
          .format(clean, len(runs)))

    sources = Counter(inf.get("source")
                      for r in runs for inf in r.get("influences") or [])
    if sources:
        print("\n  influence sources, most frequent first:")
        for src, n in sources.most_common():
            share = 100.0 * n / len(runs)
            print("    {:<22} {:>3} run(s)  {:>5.1f}%   {}".format(
                src, n, share, KNOWN_SOURCES.get(src, "(unrecognised source)")))

    # The signal that matters most: a source that shows up in nearly every run
    # is no longer an influence, it is an unexamined premise.
    pervasive = [s for s, n in sources.items() if n >= max(3, 0.6 * len(runs))]
    if pervasive:
        print("\n  ** PERVASIVE -- present in 60%+ of runs: {}".format(
            ", ".join(sorted(pervasive))))
        print("     At this frequency it is not occasional context, it is a")
        print("     standing premise. Either promote it to an explicit intake")
        print("     slot, or establish that it does not affect findings.")

    undisclosed = [(r, inf) for r in runs for inf in r.get("influences") or []
                   if not inf.get("disclosed")]
    if undisclosed:
        print("\n  ** {} influence(s) NOT disclosed in their report:"
              .format(len(undisclosed)))
        for r, inf in undisclosed[:8]:
            print("     [{}] {}: {}".format(
                r.get("agent"), inf.get("source"), (inf.get("effect") or "")[:60]))

    fills = [(r, f) for r in runs for f in r.get("unasked_fills") or []]
    if fills:
        print("\n  ** {} fact(s) supplied without being asked. Each is a "
              "candidate intake slot:".format(len(fills)))
        counts = Counter(f.get("fact") for _, f in fills)
        for fact, n in counts.most_common(10):
            print("     {:>3}x  {}".format(n, fact))

    # Topic drift: terms recurring across queries suggest the agent is being
    # asked -- or is answering -- within a narrowing band.
    terms = defaultdict(int)
    for r in runs:
        for w in {w.strip(".,;:()").lower()
                  for w in (r.get("query") or "").split() if len(w) > 4}:
            terms[w] += 1
    recurring = sorted(((n, t) for t, n in terms.items() if n >= max(3, len(runs) // 3)),
                       reverse=True)[:8]
    if recurring and len(runs) >= 5:
        print("\n  recurring query terms ({} runs): {}".format(
            len(runs), ", ".join("{} x{}".format(t, n) for n, t in recurring)))
        print("     Expected for a focused lab. Worth a look only if a run")
        print("     OUTSIDE this band came back inside it anyway.")

    print()
    return 0


# --------------------------------------------------------------------------

def cmd_status(args) -> int:
    cfg = load_config()
    runs = read_log()
    asked_in = cfg.get("session")

    if getattr(args, "session", None):
        # The agent asks once per session. This answers "must I ask?" directly,
        # so no workflow has to reimplement the comparison.
        same = asked_in == args.session
        print("session        : {}".format(args.session))
        print("asked already  : {}".format("yes" if same else "NO -- ask now"))

    print("bias reporting : {}".format(
        "ENABLED" if cfg.get("enabled") else "disabled (default)"))
    print("last set       : {}{}".format(
        cfg.get("changed", "never"),
        " (session {})".format(asked_in) if asked_in else ""))
    print("log            : {} ({} run(s))".format(
        LOG if LOG.exists() else "not created yet", len(runs)))
    return 0


def cmd_set(args) -> int:
    """Record the user's answer. Called BY THE AGENT after asking -- the user
    should never have to type a command to turn this on or off."""
    on = args.enabled == "true"
    cfg = load_config()
    cfg["enabled"] = on
    cfg["changed"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if getattr(args, "session", None):
        cfg["session"] = args.session
    save_config(cfg)
    print("bias reporting {}".format("ENABLED" if on else "disabled"))
    if on:
        print("Reports will carry a Context & Influence section, and each run "
              "is logged to bias/log.jsonl.")
    return 0


def cmd_toggle(args, on: bool) -> int:
    args.enabled = "true" if on else "false"
    return cmd_set(args)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("status", help="is reporting on, and was it already "
                                       "asked this session")
    st.add_argument("--session", help="session id; reports whether this "
                                      "session has already been asked")

    se = sub.add_parser("set", help="record the user's answer (called by the "
                                    "agent after asking, not by the user)")
    se.add_argument("--enabled", choices=["true", "false"], required=True)
    se.add_argument("--session", help="session id this answer belongs to")

    sub.add_parser("enable", help="turn reporting on")
    sub.add_parser("disable", help="turn reporting off")

    a = sub.add_parser("append", help="log one run (JSON on stdin or --file)")
    a.add_argument("--file", help="path to the run record; omit to read stdin")

    s = sub.add_parser("summarize", help="cross-run view")
    s.add_argument("--agent", choices=AGENTS)
    s.add_argument("--last", type=int, default=0, help="only the last N runs")

    args = ap.parse_args()
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "set":
        return cmd_set(args)
    if args.cmd == "enable":
        return cmd_toggle(args, True)
    if args.cmd == "disable":
        return cmd_toggle(args, False)
    if args.cmd == "append":
        return cmd_append(args)
    if args.cmd == "summarize":
        return cmd_summarize(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
