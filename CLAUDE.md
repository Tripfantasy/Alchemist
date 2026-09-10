# Alchemist — repo root

This is the router level. Three self-contained agents live below it:

| Directory | Command | Handles |
| --- | --- | --- |
| `distill/` | `/distill <topic>` | Researching a topic from the literature |
| `brew/` | `/brew <paper>` | Reproducing a specific paper's methods |
| `forage/` | `/forage <goal>` | Finding data already on a Globus collection |

# Your job at this level

**Route by default. Execute only through the delegation protocol.**

A session started here works out which agent a request belongs to and hands back
the command. That remains the default and the right answer for a vague or
spanning request.

But a person who already knows which agent they want should not have to open a
different folder to use it. So `/forage`, `/brew` and `/distill` also exist at
the root, as shims onto `.claude/lib/delegate.md`, which runs the agent **in
place**.

Nothing was relaxed to make that work. Running from the root broke three
specific things, and delegation is permitted because each has a fix, not
because the concerns stopped mattering:

1. **Each agent's rules load from its own directory.** `distill/CLAUDE.md`,
   `brew/CLAUDE.md` and `forage/CLAUDE.md` carry the non-negotiables for their
   agent - provenance tiering, no-data-downloads, read-only Globus access. None
   of them is loaded here.
   -> **Step 2** reads the agent's `CLAUDE.md` explicitly and makes it outrank
   this file for the rest of the run.
2. **Each agent's first phase is an interactive intake round** whose options are
   drawn from the specific topic or paper. That is where the output's quality
   comes from, and it cannot be delegated or skipped.
   -> **Step 6.** This one was never mechanical. It is simply a rule, and
   delegation does not touch it: the intake round and the bias question both
   happen, in full.
3. **Each agent has its own venv, its own `output/`, and its own
   `.claude/settings.json`.** Work done from the root would write to the wrong
   place with the wrong interpreter, and `forage` would have no credentials at
   all.
   -> **Steps 1, 3 and 5**: move into the agent directory, mirror its env to the
   root with `.claude/lib/agent_env.py`, and keep every relative path anchored
   to the agent.

So the old blanket ban is now narrower and sharper: **never read an agent's
workflow, skill, or command file and carry it out ad hoc.** Either follow
`.claude/lib/delegate.md` start to finish, or route and hand the command back.
Half-delegating - reading the workflow but skipping the env check, the intake
round, or the `cd` - is worse than either, because the output looks like a real
run. Reading a workflow to *explain* what an agent does is still fine.

A session started in the agent's own directory gets all of this natively. That
is still the better way to work when opening the folder is practical.

# Routing

Read `.claude/skills/route/SKILL.md` for the decision rules, the ambiguous cases,
and how to handle a request that spans more than one agent.

The short version:

- A **paper** is named or supplied (DOI, URL, PMID, PDF) -> `brew`
- Asking what **already exists on the collection** -> `forage`
- Asking what is **known about a subject** from the literature -> `distill`

# What is safe to do here

- Route a request, and explain what the chosen agent will do and ask.
- Run an agent in place via `/forage`, `/brew` or `/distill`, following
  `.claude/lib/delegate.md` exactly.
- Explain the repo: layout, setup, what each agent produces, its limitations.
- Repo-wide maintenance: `.gitignore`, the root `README.md`, git operations.
- Edit an agent's own files when asked to change that agent - that is
  maintenance, not running the workflow.
- Turn bias reporting on or off, and read its cross-run summary (`bias/`).

# Root environment

`.claude/settings.json` at the root is **generated**, and gitignored. It mirrors
the agents' env blocks so a delegated run has the credentials it needs, because
Claude Code only reads settings from the directory the session started in.

```bash
python3 .claude/lib/agent_env.py sync           # after any agent's UUIDs change
python3 .claude/lib/agent_env.py check forage   # is this session usable?
```

The agents' own `settings.json` files stay the source of truth; the root only
copies. Neither subcommand ever prints a value - UUIDs are reported by name and
status only, and must never reach a transcript or a report.

Whether a `sync` takes effect in the session that ran it depends on the harness
- some re-read `settings.json` per command, some only at startup. Do not assume;
run `check` and believe it. If it still fails after a sync, the answer is
"restart the session", not an inline `export`: shell state does not survive
between Bash calls, so that will fail again later and less visibly.

# `bias/` - the one thing shared across agents

Opt-in, off by default. Records what influenced a run OTHER than the request
and that run's clarifying answers: the "About Me" profile, prior outputs, the
knowledge store, the vocabulary, earlier turns.

It lives at root rather than three times over because its whole value is the
CROSS-AGENT, cross-run view. A single disclosure looks harmless; the pattern is
the finding - a profile fact that silently answers a question in nine runs out
of ten is a standing premise, not context. That view cannot exist inside any one
agent, which is the one deliberate exception to their self-containment.

**Each agent ASKS, once per session, before it starts work** - the user never
runs a command to enable it, and the question is separate from and additional to
that agent's intake round, never taking one of its clarifying slots. The agent
records the answer to `bias/config.json` itself. Enforced identically in all
three workflows; if you change one, change all three.

Routing note: `/alchemist` cannot intercept a direct `/distill` run - the root
command is not loaded when an agent is invoked directly. That is why the ask
lives in each agent's own intake rather than here. When routing, it is worth
mentioning that the agent will ask.

This is also why delegation does not move the ask up to the root. A delegated
`/forage` reaches the same Step 0 in the same workflow file, by the same route
as a native run. One place asks, and it is the agent's - so a run started from
the root and a run started in `forage/` behave identically.

```bash
python3 bias/report.py summarize [--agent distill] [--last 20]
```

`bias/README.md` has the definition, the record shape, and the honest limits -
it is self-reported, so it is evidence for monitoring, not proof of neutrality.

# Handoffs between agents are manual, by design

There is no automatic chain. The seams need a person:

- `forage` returns file paths; `brew` needs a paper. Nothing mechanically
  bridges "this data exists" to "here is the paper that produced it".
- `distill` returns many citations; `brew` takes one. Which one is a judgment
  call.
- Most importantly, `forage`'s `inferred` tier and `brew`'s `[inferred]` steps
  exist so a guess never reads as a fact. Passing one agent's inferred output
  into another as established input would launder a guess into a premise, which
  is the failure mode this whole framework is built to prevent.

When a request spans agents, hand back an ordered sequence and say what the
person needs to decide between steps.

Delegation does not change this. `/forage` at the root runs forage and stops.
It never rolls on into `brew` because the results looked promising, and it never
carries one agent's output into another's input on the person's behalf - that is
precisely the laundering the `inferred` tiers exist to prevent. Run one, hand
back the next command, name the decision.
