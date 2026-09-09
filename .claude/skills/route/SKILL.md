---
name: route
description: Decide which Alchemist agent handles a request and return the exact command to run. Use when someone describes a research task at the repo root and it is not yet clear whether it belongs to distill, brew, or forage; asks which agent to use, where to start, or how the agents relate; or makes a request that spans more than one of them. Also use for questions about what each agent does or produces without running it.
---

# Routing

Identify the right agent, hand back the command, stop. You are not running the
workflow — see the root `CLAUDE.md` for why that constraint exists.

## The one question that decides it

**What is the anchor of the request?**

| Anchor | Agent | Command |
| --- | --- | --- |
| A specific paper — DOI, URL, PMID, or a PDF | `brew` | `/brew <paper> <what you want from it>` |
| The lab's own existing data | `forage` | `/forage <goal>` |
| A subject, with no specific paper or local dataset in view | `distill` | `/distill <topic>` |

Signals, in case the anchor is not obvious:

- **`brew`** — "reproduce", "re-run", "reanalyze", "what does Fig. 2 take",
  "is this paper's methods complete", "turn this into a protocol", "pull the
  GEO data from this paper", any accession named *with* a paper.
- **`forage`** — "do we already have", "what's on the collection", "did anyone
  generate", "before I run a new experiment", "what data exists for X",
  anything about the knowledge store, undocumented files, or organization debt.
- **`distill`** — "what do we know about", "state of the field", "compare these
  methods so I can pick one", "background for a grant", "is this claim
  supported", a literature review.

## How to reply

Keep it to a few lines:

1. The agent, and one sentence on why that one.
2. The commands to run, exactly — including the `cd`, since a session must start
   inside the agent's directory.
3. What the agent will ask first, so the intake round is not a surprise.

```
cd brew && claude
/brew https://doi.org/10.xxxx/yyyy   what does Fig. 2 take to redo?
```

If the agent's venv may not exist yet, add the one-time setup line:

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

Then say what happens next: each agent asks 3–4 intake questions in a single
round before doing any work, and those answers determine what the output covers.

## Ambiguous cases

**"What do we know about X, and do we have any data on it?"**
Two agents. Send them to `forage` first — it is local, needs no web access, and
finishes in minutes; knowing what is already on the collection usually reframes
the literature question. Then `distill` for the literature.

**"Can I reproduce this paper with our own data?"**
`brew`, anchored on the paper. Note that `forage` can separately tell them
whether the lab holds comparable local data, but that is a second, independent
question — `brew` reproduces the paper from the paper's *own* deposited data.

**"Find me a paper about X and reproduce it."**
`distill` first, then `brew` on whichever paper they pick. Be explicit that
*they* pick — `distill` returns many citations and choosing among them is a
judgment call, not a step to automate.

**"What data should I generate next?"**
`forage`. Its report's §3 is exactly this: what the existing data cannot answer,
separated into unanswerable, never-delivered, absent, and undocumented — each
with a different remedy.

**A bare accession with no paper (e.g. "GSE123456").**
`brew` — its data half handles accessions directly. Worth confirming they want
the ETL and notebook rather than a literature summary.

**Something none of the three handle** — writing new analysis code, running an
analysis, managing the Globus collection's contents, wet-lab planning from
scratch. Say so plainly and point at what the closest agent *does* do. Do not
stretch a request to fit an agent.

## Requests that span agents

Give an ordered sequence with the decision points named:

```
1. cd forage && claude   ->  /forage <goal>
   You decide: which of the returned datasets is worth pursuing.
2. cd distill && claude  ->  /distill <refined topic>
   You decide: which paper from the citations to reproduce.
3. cd brew && claude     ->  /brew <that paper>
```

Say plainly that the handoffs are manual and why: each agent labels what it
inferred rather than observed, and feeding one agent's inference to another as
established fact would erase that distinction.

Never run a sequence yourself, and never carry an agent's output into another
agent's input on the person's behalf.
