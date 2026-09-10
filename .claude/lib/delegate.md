# Delegation protocol

How a session started at the repo root runs an agent **in place**, without
losing the things that make the agent's output trustworthy.

This file is the single source of truth for the procedure. `/forage`, `/brew`
and `/distill` at the root are thin shims that point here — if you change the
protocol, change it once, here.

Throughout, `<agent>` is one of `distill`, `brew`, `forage`.

---

## Why this is not just "read the workflow and do it"

Running an agent from the root used to be forbidden outright, because three
things silently break. Delegation is allowed now because each of the three has
a step below that actually fixes it — not because the concerns went away. If
you cannot complete a step, stop and say so; do not proceed degraded.

| What breaks at the root | Fixed by |
| --- | --- |
| The agent's `CLAUDE.md` is not loaded, so its non-negotiables are absent | Step 2 |
| Its `.claude/settings.json` env is not loaded, so credentials are unset | Step 3 |
| Relative paths resolve to the root: wrong venv, wrong `output/` | Step 1 + Step 5 |

The fourth reason — the interactive intake round — was never a mechanical
problem. It is a rule, and it is in Step 6.

---

## Step 1 — Move into the agent directory

One standalone `cd` to the absolute path, as its own Bash call. The harness
keeps the working directory across later calls; a `cd` chained into a compound
command does not, and can trigger a permission prompt.

```bash
cd /absolute/path/to/repo/<agent>
```

Confirm it worked (`pwd`) before going on. Everything after this depends on it.

## Step 2 — Load the agent's rules

Read `<agent>/CLAUDE.md` in full, by absolute path, before anything else.

**For the rest of this run it outranks the root `CLAUDE.md`.** Where they
conflict — and they do, since the root's default is "route, do not execute" —
the agent's file wins. Read it as binding instruction, not as background.

Reading files under `<agent>/` normally causes Claude Code to load that nested
`CLAUDE.md` on its own. Do not rely on that having happened. Read it explicitly.

## Step 3 — Verify the environment

```bash
python3 ../.claude/lib/agent_env.py check <agent>
```

- **Exit 0** — continue.
- **Non-zero** — the session is missing the agent's credentials. Run the `sync`
  it names, then **run `check` again**. If it now passes, carry on; some
  harnesses re-read `settings.json` per command rather than only at startup. If
  it still fails, stop and tell the user to restart the session — a sync cannot
  help a session that reads settings only once.

Either way, do not work around a failing check by exporting variables inline.
Shell state does not survive between Bash calls, so it will fail again a few
steps later, further in, and less obviously.

The check prints variable names and a status only, never values. Keep it that
way — infrastructure UUIDs must not reach a transcript or a report.

## Step 4 — Hand off to the agent's own command file

Read `<agent>/.claude/commands/<agent>.md` and follow it, treating the
arguments passed to the root shim as its `$ARGUMENTS`.

Do not reimplement it, summarise it, or work from what you remember of it. That
file points at the agent's workflow in `workflows/`, which is the real single
source of truth; let it do that. If anything in this protocol conflicts with the
workflow, **the workflow wins** — the only exceptions are Steps 1–3, which are
about making the root session equivalent to a session started in the agent
directory, not about the procedure itself.

## Step 5 — Relative paths mean the agent directory

Every relative path in the agent's `CLAUDE.md`, command file, workflows and
skills is written for a session whose working directory is the agent's. After
Step 1 that is true for Bash, so the documented commands run verbatim:

```bash
./.venv/bin/python scripts/scan_endpoint.py ...   # the agent's venv
python3 ../bias/report.py status ...              # the shared, root-level bias log
```

Two things do not follow the working directory, so handle them by hand:

- **The Read/Write/Edit tools take absolute paths.** When a workflow says
  "read `resources/report_template.md`", that is
  `<repo>/<agent>/resources/report_template.md`.
- **`output/` is the agent's**, never the root's. Deliverables land in
  `<repo>/<agent>/output/`. So does the `.pdf`.

Never use bare `python3` for an agent's own scripts — only `./.venv/bin/python`.
The dependencies are installed per agent, and the root has no venv at all. The
one exception is the shared `bias/report.py` and this directory's `agent_env.py`,
which are deliberately standard-library-only so they run under any interpreter.

## Step 6 — The intake round and the bias question still happen

Both. In full. They are the point, not overhead.

- The **bias-reporting question** is asked once per session, before intake, as
  its own separate question. Record the answer with `bias/report.py` yourself;
  never tell the user to run a command.
- The **intake round** is 3–4 questions in one round, with options drawn from
  the actual topic, paper or collection in front of you. It never gets merged
  into the bias question, trimmed to save a turn, or answered on the user's
  behalf from their profile or from earlier conversation.

Delegation changes where the agent runs. It changes nothing about what it asks.

## Step 7 — Say where you are

Tell the user, in one line, that you are running `<agent>` in place from the
root, and that its rules are loaded. A delegated run and a native one should be
distinguishable in the transcript — if something looks wrong later, the first
question will be which one this was.

---

## What delegation still does not do

**It does not chain agents.** One `/forage` runs forage. If the result suggests
a `brew` follow-up, hand back the command and what the user needs to decide
first. The handoffs are manual by design, and the root `CLAUDE.md` explains why:
`forage`'s `inferred` tier and `brew`'s `[inferred]` steps exist so a guess never
reads as a fact, and feeding one agent's inference into another as established
input would launder it into a premise.

**It does not make the root a better place to work than the agent directory.**
A session started in `<agent>/` gets all of this natively, with the agent's
skills auto-triggering and no protocol to follow. Delegation exists because
opening a different folder is not always practical — not because it is equal.
