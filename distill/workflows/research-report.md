# Workflow: Research Report

**Purpose:** Take any topic, research it thoroughly, and produce a credible, cited, scannable report that ends in actionable recommendations.

**Invoke with:** `/distill <topic>` — or just say "follow the research-report workflow on <topic>".

**Inputs:** a topic (anything, any field).
**Output:** two files — `output/YYYY-MM-DD_<topic-slug>.md` and the matching `.pdf`. The Markdown is the source of truth; the PDF is what gets circulated.

This workflow inherits the rules in `CLAUDE.md` — ask before starting, show the plan, bullets over paragraphs, output to `output/`, cite sources. Don't restate them; follow them.

**Tool note:** this workflow needs `WebSearch` and `WebFetch`. If they aren't loaded, fetch them first with `ToolSearch` using the query `select:WebSearch,WebFetch`.

---

## Phase 0 — Intake

**Never skip this phase.** Not when the topic looks self-explanatory, not when you think you already know what's wanted, not when the request already contains some detail. The whole value of this workflow is that research targets the right thing on the first pass.

Ask **one** batched round using `AskUserQuestion` — 3 or 4 questions in a single call, then start working. No second round, no follow-up trickle.

### 0a. The bias-reporting question — separate, and additional

Asked once per session, before the topic round.

**It does not use a topic slot.** It is a separate `AskUserQuestion` call with a
single question, and the topic round that follows still gets its full 3–4
questions. Never drop, merge, or shorten a topic slot to make room for it — the
topic slots are what determine whether the research targets the right thing, and
a session-level preference must never be paid for out of that budget.

Check whether this session has already been asked:

```bash
python3 ../bias/report.py status --session <session-id>
```

- **`asked already : yes`** — do not ask again. Use the reported state and go
  straight to the topic round.
- **`asked already : NO`** — ask, in one question:

> Enable bias reporting for this session?
> - **No** — the default. Reports carry no influence section
> - **Yes** — each report gains a *Context & Influence* section listing what shaped it besides your request, and runs accumulate in `bias/log.jsonl` for a cross-run view

Then record the answer yourself — **never ask the user to run a command**:

```bash
python3 ../bias/report.py set --enabled true|false --session <session-id>
```

If you cannot determine a session id, treat "have I already asked in this
conversation?" as the test: your own context shows whether you did. Ask on your
first agent run in the conversation, and not again after that.

If the user already said in this conversation whether they want it, that answer
stands — record it and skip the question.

### Before you write the questions: you have no prior

You are starting from the request in front of you, and nothing else. Not this repo's other reports, not what previous topics suggest the user cares about, not the "About Me" in `CLAUDE.md`. Those describe *who is asking*; they do not narrow *what was asked*.

Two specific prohibitions, because both have happened:

- **Do not read local files to shape the search.** No `Glob` or `Grep` across the filesystem, no reading `output/` for related past reports, no scanning a working directory for context — unless the user opts in through slot P below and names a path. `Read`/`Glob`/`Grep` are for this project's own `resources/` and for writing the deliverable, not for building an unrequested prior.
- **Do not let a standing profile supply an answer a slot should ask for.** "They work in neuroscience, so this is about mouse" is exactly the inference that makes a report answer the wrong question. If organism matters, slot S asks.

If the request genuinely does carry a detail, use it and drop that slot (see intake rules) — the point is that a detail must come from *the request*, not from around it.

### The rule that matters most: options must come from the topic

Generic options waste the round. "Broad vs. narrow", "Technical vs. accessible", "Recent vs. comprehensive" tell you almost nothing, because the user has to translate them into their actual situation anyway. Every option must be a concrete choice a person familiar with *this specific topic* would recognize.

Do this by spending 30 seconds thinking about the topic's real dividing lines before writing options — what are the actual sub-fields, competing approaches, or scope boundaries someone would care about here?

**Bad** (generic, could be attached to any topic):
> How broad should the scope be?
> - Broad overview
> - Narrow deep-dive
> - Balanced

**Good** (topic: *CRISPR base editing for neurodegenerative disease*):
> Which part of the pipeline should this cover?
> - **Editing chemistry only** — base vs. prime editors, on/off-target profiles, no delivery
> - **Delivery-focused** — AAV, LNP, and BBB-crossing strategies for CNS
> - **Full path to clinic** — chemistry + delivery + the current trial landscape
> - **Target selection** — which neurodegenerative mutations are actually addressable

### Choosing the questions

You have four slots and more than four candidates, so the round is **selected, not fixed**. Two slots are mandatory, one is conditional, and the rest fill whatever room is left.

**Always ask:**

| Slot | Header | What it establishes |
|---|---|---|
| **P** | `Prior` | Whether the search may reference anything local, or literature only. See below — this one is never skipped and never assumed |
| **Q** | `Questions` | The 2–4 concrete sub-questions to answer, and **what decision this informs** |

**Ask when it fires:**

| Slot | Header | Fires when |
|---|---|---|
| **S** | `Sample` | The topic references the user's own analysis output — see "Analytical priors" below |

**Fill remaining slots from:**

| Slot | Header | What it establishes |
|---|---|---|
| `Scope` | Boundaries — which subtopics are in and out, time window, and any domain/system limits |
| `Audience` | Who reads it, and how deep it goes (see depth tiers below) |
| `Emphasis` | The angle — mechanism, methods comparison, tool selection, state-of-field, or controversies |

Slot Q is the one that makes the report *useful* rather than merely informative — the answer drives the Recommendations section at the end. Push for a real decision ("which aligner do we adopt", "is this worth a rotation project") rather than a vague interest.

When slot S fires it displaces `Emphasis` first, then `Audience`. Never drop P or Q to make room; if you are somehow over four, the topic needs a narrower request, not a bigger round.

### Slot P — the local prior is opt-in, always

The default is literature only. A local file or directory enters the search **only** because the user said so in this round.

This slot exists because the alternative failed: reading nearby files "for context" quietly reweights the search terms, the sub-questions, and even the options offered in this very round — and the user never sees it happen or gets to decline it. Asking costs one slot; not asking costs the run's neutrality.

Ask it plainly, and take the path as free text:

> Should this search reference anything local, or literature only?
> - **Literature only** — nothing on disk is read; the report reflects published sources
> - **A local file** — a manuscript draft, a results table, a marker list
> - **A local directory** — a project folder to read for context
>
> *(Choose a local option and give the path in "Other", or answer "Other" directly with the path.)*

Then:

- **"Literature only"** — read nothing outside this project's `resources/`. Say so in the report's Scope line: *Local prior: none*.
- **A path** — read it, and record in Scope exactly what you read (`Local prior: ~/proj/markers.csv — top 30 markers × 12 clusters`). What it contributes to the report is cited as a local prior, never as literature, and never counted in the source total.
- **No answer / the round was skipped by the user** — literature only. Silence is not consent to read the filesystem.

### Analytical priors — slot S

**The trigger.** The topic references output the user already produced, rather than a subject in the literature. Signals: *top N markers per cluster*, *my DE genes*, *these peaks*, *cluster 7*, *my UMAP*, *annotate these*, a pasted gene list, a results table.

**Why it gets its own slot.** Interpreting analysis output is undecidable without the sample it came from. The same marker set annotates to different cell types in mouse OE versus human cortex, at E14 versus P60, in wild-type versus knockout. Without those facts the report can only hedge — and hedging is what this slot exists to prevent.

**The failure this replaces.** A report that reaches Findings and says *"the annotation is ambiguous — this depends on tissue and developmental stage"* has not discovered an ambiguity. It has deferred a question that intake should have asked, and it has spent the whole search budget on a question nobody can answer. **If you find yourself about to write that sentence, Phase 0 failed.** The ambiguity was resolvable at zero cost, twenty minutes earlier.

**What to ask.** One slot, four facts. Do not ask four questions — build options that carry the whole context as a profile, drawn from whatever the request already hints at:

> These markers came from which sample?
> - **Adult mouse olfactory epithelium, wild-type** — P60+, uninjured
> - **Adult mouse OE, post-injury** — methimazole or bulbectomy regeneration timecourse
> - **Embryonic/postnatal mouse OE** — E14–P7, developmental
> - **Human** — organoid or post-mortem tissue
>
> *(Answer "Other" with organism / tissue / genotype / age if none of these fit.)*

The four facts the slot must land, whatever shape the options take: **organism**, **tissue or region**, **genotype or condition**, **age or developmental stage**. If an option set cannot carry all four, say in the question text which ones you still need, and treat an "Other" free-text answer as authoritative.

Carry all four into the report's Scope section verbatim, and use them to constrain every search in Phase 2 — a marker query without the organism returns the wrong literature.

**Depth tiers** — offer these with the `Audience` slot when you ask it; otherwise infer the tier from the request and state it in Scope:

| Tier | Length | Sources | Use when |
|---|---|---|---|
| Brief | ~1 page | 5–8 | Orienting on something new, or a quick decision |
| Standard | 3–5 pages | 15–25 | The default — enough for a real decision |
| Deep | 8–12 pages | 40+ | Grant background, a review draft, a major commitment |

### Intake rules

- One round. If the answers leave something genuinely ambiguous, make a reasonable assumption, state it in the report's Scope section, and keep going.
- If an answer makes a later question moot, **drop that question** — don't pad to four.
- If the request already answers a slot clearly, drop that slot too. A two-question round is fine when the user was specific. **Slot P is the exception** — a request that says nothing about local files has not answered it, and the answer is not "probably fine either way".
- Carry every answer forward into the report's **Scope** section, close to verbatim, so the deliverable visibly answers what was asked.
- The user can always answer "Other" with free text — treat that as authoritative over the options you offered.
- **An unasked question is not an assumption you may make silently.** Anything you fill in that no answer covered goes in Scope under Assumptions, named as yours.

---

## Phase 1 — Orient, then plan

### Orient (2–3 searches)

Reconnaissance only. You are learning the shape of the field, not gathering findings yet:

- What vocabulary does this field actually use? (Your search terms are probably the outsider's terms.)
- Who are the key labs, authors, companies, or institutions?
- What are the landmark papers or turning points?
- How does the field naturally divide itself into subtopics?
- How fast does it move? (Determines what counts as "stale" in Phase 2.)

Don't take notes on substance here. This phase exists to make Phase 2's searches good.

### Plan (show it, then proceed)

Decompose the topic into **4–8 researchable sub-questions**, shaped by the Phase 0 answers. Good sub-questions are specific enough that you'd know when you'd answered one.

Show the plan before executing (`CLAUDE.md` rule) — briefly:

```
Researching: <topic>
Scope: <from intake>  ·  Depth: <tier>  ·  Target: ~N sources

Sub-questions:
1. <question>          → <search approach, source types>
2. <question>          → <search approach, source types>
...
```

Then **proceed**. Showing the plan is transparency, not a request for approval — don't wait unless the user interjects.

---

## Phase 2 — Gather

Work sub-question by sub-question. For each one:

1. Search — start with the field's own vocabulary from Phase 1.
2. Identify the 2–5 best sources, ranked by `resources/source-quality.md`.
3. **Fetch and read each one.** Search snippets are for deciding what to open, never for citing.
4. Log what you found.

### Evidence log

Keep a running log in the **session scratchpad** — not in `output/`, which holds finished deliverables only. One row per claim:

```
claim | source [n] | year | tier | supports / contradicts / mixed
```

This log is what you write the report from. It's also what makes Phase 3 possible.

### Guardrails

- **Never cite a URL you didn't fetch.** This is the single most important rule in the workflow. A plausible-looking citation that doesn't say what you claimed destroys the report's credibility, and it's the failure mode most likely to slip through.
- If you only saw an abstract, mark the claim as abstract-only — it can still be used, just labeled.
- **Always record the publication date.** For a fast-moving field, flag anything old enough to be superseded.
- When sources conflict, **capture both sides**. Don't silently pick a winner — that's Phase 3's job, and often the disagreement itself is the finding.
- Follow citation trails. A paper's references and its citing papers are usually higher-yield than another search.
- **Stop on saturation**, not on a count: when new searches keep returning sources you've already seen, that sub-question is done. If you hit the depth tier's target and searches are still turning up genuinely new material, keep going and say so.
- Track what you searched for and found *nothing* on — that's real information, and it feeds the Gaps section.
- **Constrain every search with the slot S facts when they exist.** A marker or DE-gene query without the organism, tissue and stage returns literature about a different system, and it looks correct. `Ascl1 progenitor` is a different search from `Ascl1 progenitor olfactory epithelium mouse postnatal`.
- **A local prior is a source, not a search term generator.** When slot P supplied a path, the file's content can be *compared against* the literature and cited as a local prior — it does not silently become the vocabulary you search with. If a term from the local file drives a search, say so in Scope.

---

## Phase 3 — Verify

This phase is what separates a research report from a summary. Don't compress it.

### Corroborate
Every load-bearing claim needs **2+ independent sources**. Independent means genuinely separate evidence — three news articles about one study are one source, not three. Anything still single-sourced gets labeled as such inline.

### Actively look for disconfirming evidence
Run a dedicated pass searching against your own findings: `"<claim>" limitations`, `"<claim>" criticism`, `failure to replicate <finding>`, `<method> drawbacks`. You are trying to break your own conclusions. If you find nothing after genuinely trying, that itself raises confidence — note it.

### Classify every finding

- **Established** — consensus, multiply replicated, no credible contradiction found
- **Contested** — credible sources genuinely disagree
- **Emerging** — promising but thin: preliminary, single-lab, or preprint-only

### Cut what you can't support
Any claim you can't substantiate is removed — or restated as an explicit inference with the reasoning shown ("no direct study found; this follows from X [3] and Y [7]"). Never let an inference wear a citation's clothes.

---

## Phase 4 — Write

Fill `resources/report-template.md`. Get the date from `date +%F` via Bash — never guess it.

**Filename:** `output/YYYY-MM-DD_<topic-slug>.md` (lowercase, hyphenated, short).

### Style

- **Bullets over paragraphs** (`CLAUDE.md`). Prose only where a bullet genuinely can't carry the logic.
- Every non-obvious claim carries an inline `[n]`.
- Lead with the answer. The TL;DR states conclusions, not "this report examines…".
- Numbers, dates, and effect sizes wherever you have them — specificity is credibility.
- Write for the audience named in Phase 0.

### The closing section

The report ends with **Recommendations & Next Steps**. Write it **last**, derived from the findings above it, answering the decision captured in Phase 0 question 3.

Rules:

- **Every recommendation traces to a cited finding.** No advice that appeared from nowhere.
- **Confidence is inherited from the evidence.** A Low-confidence finding cannot produce a confidently-worded recommendation. Say "worth piloting" where the evidence supports piloting, not "adopt".
- **Next steps must be doable next week** — read a specific paper, pilot a named tool, email a named lab, run a specific comparison. Never "further research is warranted"; that's filler, and it's the most common way this section goes wrong.
- **Several next steps should close a stated Gap.** That's the natural link between the two sections.
- **If the evidence doesn't support a recommendation, say so.** "The evidence doesn't yet justify committing to an approach — here's what would change that" is a legitimate, useful answer. Manufacturing advice to fill a heading is not.
- Tailor to the audience and decision from Phase 0. A PI choosing a direction needs different recommendations than a lab member picking a tool.

---

## Phase 5 — Self-check, then deliver

Run this checklist before handing anything over. Fix what fails.

- [ ] Every Phase-0 question actually answered somewhere in the report?
- [ ] Slot P recorded in Scope — either *Local prior: none*, or the exact path and what it contributed?
- [ ] Nothing outside `resources/` read from disk unless slot P authorized it?
- [ ] If slot S fired: organism, tissue, genotype and stage all in Scope, and all four used to constrain the Phase 2 searches?
- [ ] **No finding hedged on a fact intake could have established.** Search the draft for "depends on the tissue", "if this is mouse", "ambiguous without" — each hit is a Phase 0 miss, not a finding
- [ ] Every claim either cited, or explicitly marked as inference?
- [ ] Every source in the list genuinely fetched and read?
- [ ] Contested findings labeled as contested — not flattened into false consensus?
- [ ] Gaps section honest about what wasn't found, including searches that came up empty?
- [ ] Every recommendation traceable to a cited finding, and carrying a confidence level?
- [ ] Next steps concrete and doable — nothing reducing to "more research is needed"?
- [ ] File in `output/` with the right name and date?

### Render the PDF

Every report ships as **both** Markdown and PDF. Once the checklist above passes and the `.md` is final, run:

```
python3 resources/md-to-pdf.py output/YYYY-MM-DD_<topic-slug>.md
```

It writes the `.pdf` beside the `.md` and prints the path and size.

- **Render last**, after the self-check — a PDF built from an unfixed draft only has to be rebuilt.
- **If you touch the `.md` afterwards, re-run the script.** A stale PDF that disagrees with its Markdown is worse than no PDF at all.
- Needs Google Chrome and the `markdown` Python package. Don't improvise a different converter: one pipeline is what keeps every report in `output/` looking alike.
- Sanity-check the result — page count is plausible, and tables rendered as tables rather than leftover `|` pipes.

#### Interpreter gotcha (resolved 2026-09-08 — don't rediscover this)

`markdown` is installed for the **system** Python only:
`/usr/bin/python3` (3.9.6) → `~/Library/Python/3.9/lib/python/site-packages`.

The `python3` first on PATH is miniconda (`~/miniconda3/bin/python3`, 3.12.9) and does **not**
have it. A bare `python3 resources/md-to-pdf.py …` used to fail with
`error: missing dependency`.

- **This is already fixed.** The script now detects the failed import and re-execs itself under
  `/usr/bin/python3`, printing a `note:` to stderr. The command above works from either interpreter.
- **So a missing-`markdown` error is not a reason to pip-install anything.** It means the system
  interpreter lost the package. Check `/usr/bin/python3 -c "import markdown"` *before* installing —
  Chrome and the package were both already present when this was first hit.
- Verifying tables: don't try to grep text out of the finished PDF. Chrome embeds subsetted fonts
  with custom encodings, so naive extraction returns garbage and every probe reads as absent. Check
  at the HTML stage instead — run the source through `markdown.markdown(...)` with the same
  extensions and count `<table>` / `<td>` tags.

### Bias reporting (if it was enabled in Phase 0)

Only when the Phase 0 question turned it on. Append a **Context & Influence**
section to the report, then log the run:

```bash
python3 ../bias/report.py append --file <scratchpad>/bias_run.json
```

`../bias/README.md` has the section format and the record shape. What this
workflow contributes to it:

- Slot P's answer, and whether anything was actually read from disk
- Slot S's four facts, and whether any of them were assumed rather than answered
- Any point where the `CLAUDE.md` profile — bioinformatics, neuroscience, this
  department — supplied something the intake round did not

**"(none)" is the expected answer for a clean run.** Do not manufacture an
influence to look thorough; a log padded with non-influences cannot show drift.

### Report back in chat

Short. Don't paste the report into the terminal:

- The file paths (`.md` and `.pdf`)
- 3–5 bullet headline findings
- The top recommendation
- Overall confidence, and the biggest caveat

### Optional

**Offer**, don't auto-run: publishing the report as a shareable Artifact page for lab members or the department. Only do it if asked.

---

## Notes for maintaining this workflow

- Phase 0's topic-specific options are the highest-leverage part. If a run goes sideways, that's usually where.
- The Recommendations section is where generic filler creeps in. Check it hardest.
- Slots P and S were added after two real failures (issues #1 and #5). P: runs were scanning local directories unprompted, which reweighted the search *and* the intake options themselves, invisibly. S: a cluster-annotation run reported the annotation as ambiguous pending tissue and organism — facts one question would have supplied before any search ran. Both are the same bug seen twice: context that should have been asked for was assumed instead. If a fifth slot is ever proposed, check first whether it is a third instance of that same bug.
- Once the PubMed / bioRxiv / Scite connectors are authorized in claude.ai settings, Phase 2 can use them directly for structured literature search instead of scraping the open web — a drop-in upgrade, no other phase changes.
