# Alchemist — repo root

This is the router level. Three self-contained agents live below it:

| Directory | Command | Handles |
| --- | --- | --- |
| `distill/` | `/distill <topic>` | Researching a topic from the literature |
| `brew/` | `/brew <paper>` | Reproducing a specific paper's methods |
| `forage/` | `/forage <goal>` | Finding data already on a Globus collection |

# Your job at this level

**Route, do not execute.** A session started here identifies which agent a
request belongs to and hands back the exact command to run. It does not do the
agents' work.

That is a deliberate constraint, not a limitation to work around:

1. **Each agent's rules load from its own directory.** `distill/CLAUDE.md`,
   `brew/CLAUDE.md` and `forage/CLAUDE.md` carry the non-negotiables for their
   agent - provenance tiering, no-data-downloads, read-only Globus access. None
   of them is loaded here. Working from the root means working without them.
2. **Each agent's first phase is an interactive intake round** whose options are
   drawn from the specific topic or paper. That is where the output's quality
   comes from, and it cannot be delegated or skipped.
3. **Each agent has its own venv and its own `output/`.** Work done from the root
   would write to the wrong place with the wrong interpreter.

So: never read `brew/workflows/paper_reproduction.md` (or any agent's workflow,
skill, or command file) in order to carry out that workflow yourself. Reading one
to *explain* what an agent does is fine.

# Routing

Read `.claude/skills/route/SKILL.md` for the decision rules, the ambiguous cases,
and how to handle a request that spans more than one agent.

The short version:

- A **paper** is named or supplied (DOI, URL, PMID, PDF) -> `brew`
- Asking what **already exists on the collection** -> `forage`
- Asking what is **known about a subject** from the literature -> `distill`

# What is safe to do here

- Route a request, and explain what the chosen agent will do and ask.
- Explain the repo: layout, setup, what each agent produces, its limitations.
- Repo-wide maintenance: `.gitignore`, the root `README.md`, git operations.
- Edit an agent's own files when asked to change that agent - that is
  maintenance, not running the workflow.
- Turn bias reporting on or off, and read its cross-run summary (`bias/`).

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
person needs to decide between steps. Do not run the steps.
