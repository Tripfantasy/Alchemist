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

### The four questions

Use these slots. Adapt the wording to the topic; keep the intent.

| # | Header | What it establishes |
|---|---|---|
| 1 | `Scope` | Boundaries — which subtopics are in and out, time window, and any domain/system/organism limits |
| 2 | `Audience` | Who reads it, and how deep it goes (see depth tiers below) |
| 3 | `Questions` | The 2–4 concrete sub-questions to answer, and **what decision this informs** |
| 4 | `Emphasis` | The angle — mechanism, methods comparison, tool selection, state-of-field, or controversies |

**Depth tiers** — offer these in question 2, with the audience:

| Tier | Length | Sources | Use when |
|---|---|---|---|
| Brief | ~1 page | 5–8 | Orienting on something new, or a quick decision |
| Standard | 3–5 pages | 15–25 | The default — enough for a real decision |
| Deep | 8–12 pages | 40+ | Grant background, a review draft, a major commitment |

Question 3 is the one that makes the report *useful* rather than merely informative — the answer drives the Recommendations section at the end. Push for a real decision ("which aligner do we adopt", "is this worth a rotation project") rather than a vague interest.

### Intake rules

- One round. If the answers leave something genuinely ambiguous, make a reasonable assumption, state it in the report's Scope section, and keep going.
- If an answer makes a later question moot, **drop that question** — don't pad to four.
- If the request already answers a slot clearly, drop that slot too. A two-question round is fine when the user was specific.
- Carry every answer forward into the report's **Scope** section, close to verbatim, so the deliverable visibly answers what was asked.
- The user can always answer "Other" with free text — treat that as authoritative over the options you offered.

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
- Once the PubMed / bioRxiv / Scite connectors are authorized in claude.ai settings, Phase 2 can use them directly for structured literature search instead of scraping the open web — a drop-in upgrade, no other phase changes.
