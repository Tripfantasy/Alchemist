---
description: Work out which Alchemist agent handles a task and return the command to run
argument-hint: "<what you are trying to do>"
---

Route this request to the right agent.

**Read `.claude/skills/route/SKILL.md` now and follow it.** That file holds the
decision rules, the ambiguous cases, and how to handle a request spanning more
than one agent.

## The request

$ARGUMENTS

If that is empty, ask what they are trying to do before routing anything.

## Rules

- **Route, do not execute.** Hand back the agent, the `cd`, and the command.
  Never carry out the agent's workflow from here — the root `CLAUDE.md` explains
  why, and the reasons are load-bearing.
- Name what the agent will ask first, so the intake round is expected. That
  includes the bias-reporting question: every agent asks it once per session
  before starting, as a separate question that does not consume an intake slot.
  Do not answer it on the user's behalf, and do not tell them to run a command —
  the agent asks and records it itself.
- If the request spans agents, give an ordered sequence and say what the person
  decides between steps. The handoffs are manual by design.
- If none of the three fit, say so and point at what the nearest one actually
  does. Do not stretch a request to fit an agent.
