---
name: route
description: Decide which Alchemist agent handles a request and return the exact command to run. Use when someone describes a research task at the repo root and it is not yet clear whether it belongs to distill, brew, or forage; asks which agent to use, where to start, or how the agents relate; or makes a request that spans more than one of them. Also use for questions about what each agent does or produces without running it.
---

# Routing

Identify the right agent and hand back the command.

Routing is for when the agent is *not yet settled* — a vague request, one that
spans two agents, or a question about which to use. Once it is settled, the
person can run it right here: `/forage`, `/brew` and `/distill` exist at the
root and delegate in place via `.claude/lib/delegate.md`.

So do not answer a clear, well-formed request with instructions to go somewhere
else. If someone says "find our existing data on X", that is `/forage <X>` —
offer to run it, do not hand them a folder to open. Keep the pure-routing reply
for the cases below, where the point is the decision, not the execution.

You never run a workflow ad hoc. Either delegate through the protocol or route.
The root `CLAUDE.md` has the reasoning.

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
2. The command, exactly as they can run it from here.
3. What the agent will ask first, so the intake round is not a surprise.

```
/brew https://doi.org/10.xxxx/yyyy   what does Fig. 2 take to redo?
```

That runs from the root, delegating in place. There is **no `cd brew && claude`
step** — that instruction used to be here and it never worked, because this
setup has no `claude` CLI on the PATH. The alternative to delegation is opening
the agent's folder as the editor's workspace and starting a session there, which
is worth mentioning only if they ask for it or delegation fails.

If the agent's venv may not exist yet, add the one-time setup line:

```bash
python3 -m venv brew/.venv && ./brew/.venv/bin/pip install -r brew/requirements.txt
```

For `forage` specifically, a root session also needs the collection credentials
mirrored in. `.claude/lib/agent_env.py check forage` says whether this one has
them; if not, `sync` and restart the session.

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
1. /forage <goal>
   You decide: which of the returned datasets is worth pursuing.
2. /distill <refined topic>
   You decide: which paper from the citations to reproduce.
3. /brew <that paper>
```

Say plainly that the handoffs are manual and why: each agent labels what it
inferred rather than observed, and feeding one agent's inference to another as
established fact would erase that distinction.

Delegation makes each step runnable from here; it does not join them up. Run
step 1 if they ask for it, then **stop** and put step 2 back in their hands.
Never run a sequence straight through, and never carry an agent's output into
another agent's input on the person's behalf — the fact that it is now
mechanically easy to do so is exactly why the rule is worth restating.
