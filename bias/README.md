# Bias reporting

Opt-in, off by default. Records what influenced a run **other than the request
and the answers to that run's clarifying questions**.

## What "bias" means here

Narrow and specific: **the agent steering off a standing picture of the user
rather than off this instance's query.**

Sources, all of them real in this repo:

| Source | Where it leaks from |
| --- | --- |
| `claude_md_profile` | The "About Me" block — neuroscience, bioinformatics, this department. Says who is asking, not what was asked |
| `prior_output` | Reports already in an agent's `output/`, read "for context" |
| `local_file` | Files read off disk that no intake answer authorized |
| `knowledge_store` | forage's `query_log.jsonl` and association store — literally a record of previous questions |
| `vocab` | forage's `vocab.json`, seeded from one lab's CSV, with refusals tuned to one collection |
| `method_gaps` | brew's accumulating notes on what a given lab habitually omits |
| `conversation_history` | Earlier turns in the same session, when the current request is independent of them |
| `memory` | Anything recalled about the user from a previous session |

None of these is illegitimate on its own. A vocabulary is *supposed* to
accumulate; so are correction labels. The bias question is narrower:

> Did this run reach a conclusion the request and its intake answers do not
> support, because a standing prior supplied the difference?

## The two questions it answers

**Per run:** what shaped this output besides what I asked for? Answered by the
**Context & Influence** section the agent appends to the report.

**Across runs:** is the agent converging on a preconceived model of me? A single
run's disclosure looks harmless in isolation. The pattern is the finding —
fifteen runs where the profile supplied the organism, and the one run about a
non-mouse system quietly got mouse literature.

That second question is why the log accumulates, and it is the reason this
exists as a store rather than a per-report footnote.

## Honest limits

**This is self-reported, so it catches what the agent noticed.** An influence
that never surfaced as a decision does not appear here. The log is evidence for
monitoring, not proof of neutrality, and a clean log is not the same as a clean
run.

Two things partly compensate:

- The cross-run view surfaces drift that no single self-report shows.
- Every agent already logs its intake questions and answers. An influence with
  no corresponding intake answer is visible as a gap between them, whether or
  not the agent flagged it.

## Turning it on

**You do not run a command.** Each agent asks, once per session, before it
starts work:

> Enable bias reporting for this session?
> - **No** — the default. Reports carry no influence section
> - **Yes** — each report gains a *Context & Influence* section, and runs accumulate for the cross-run view

Answer once and every agent in that session honors it; a new session asks again.
The agent writes your answer to `bias/config.json` itself.

Two rules the agents follow, and which any change here must preserve:

- **The question never costs an intake slot.** It is a separate, additional
  `AskUserQuestion` call. The topic/paper/goal round still gets its full 3–4
  questions, because those are what decide whether the work targets the right
  thing. A session preference is not paid for out of that budget.
- **The user is never asked to run a command** to enable, disable, or inspect
  this. If you find yourself writing "run `python3 bias/report.py …`" in a
  message to the user, that is the bug.

The CLI below exists for the agent, and for you when you want the cross-run view:

```bash
python3 bias/report.py status --session <id>   # has this session been asked?
python3 bias/report.py set --enabled true --session <id>   # agent records the answer
python3 bias/report.py summarize               # the cross-run view
python3 bias/report.py enable | disable        # manual override, if you want one
```

## What an agent does when it is enabled

1. **At intake:** note which slots were asked and what came back.
2. **Throughout:** when a decision is made on something *other* than the request
   or an intake answer, record it — the source, what it supplied, and what it
   changed.
3. **In the report:** append a **Context & Influence** section (format below).
4. **At the end:** append the run to the log:

```bash
python3 bias/report.py append --file run.json
```

5. **Periodically:** `python3 bias/report.py summarize` for the cross-run view.

### The Context & Influence section

```markdown
## Context & Influence

**Asked and answered:**
- Scope → cluster annotation, marker interpretation only
- Sample → mouse · olfactory epithelium · wild-type · P60
- Prior → literature only

**Influenced this run beyond the above:**
- `claude_md_profile` — assumed a neuroscience audience, so the report
  explains bioinformatics methods and not neuroanatomy. Affected: depth and
  terminology. Not the findings.

**Filled without asking:**
- (none)
```

Rules for it:

- **"(none)" is a real and expected answer.** A run genuinely driven by its
  intake answers writes "(none)" under both headings. Manufacturing an influence
  to look thorough makes the log useless.
- **Name the effect, not just the source.** "The profile influenced framing" is
  not auditable. "Assumed mouse, so searches were mouse-restricted" is.
- **Separate what it changed from what it didn't.** An influence on the writing
  style is not the same as an influence on a finding, and flattening them hides
  the ones that matter.
- **`Filled without asking` is the highest-signal line in the section.** It is
  where issues #1 and #5 both showed up. Anything there is a candidate intake
  slot.

## Record shape

```json
{
  "agent": "distill",
  "query": "annotate these cluster markers",
  "slots": [{"header": "Sample", "answer": "mouse OE, WT, P60"}],
  "influences": [
    {"source": "claude_md_profile",
     "supplied": "assumed neuroscience audience",
     "effect": "depth and terminology; no effect on findings",
     "disclosed": true}
  ],
  "unasked_fills": [],
  "notes": ""
}
```

`run_id` and `ts` are added on append. `agent`, `query` and `influences` are
required; an empty `influences` list is valid and meaningful.
