---
name: lab-profile
description: Build a digestible profile of the lab's work - research themes and how they are approached, methods, biological focus, toolkit, a word cloud of the lab's vocabulary, and forage's progress mapping the data - as a written profile (.md + .pdf) and an interactive HTML dashboard, in internal and collaborator editions. Use when someone wants an onboarding overview for new lab members, a summary of the lab's work for collaborators, charts of the knowledge base for a presentation, or asks what the lab works on according to its data.
---

# Lab Profile

Read `workflows/lab_profile.md` and follow it. That file is the single source
of truth. Do not work from memory or paraphrase its steps.

## The things that matter most

1. **Read-only outside `sigil/`.** The only input is forage's exported
   snapshot. Never read forage's stores, never scan, never touch Globus.
2. **Soft truth, plainly stated.** Present what the lab does and what data
   exists without tier labels or hedging, but never a number the data files
   do not support.
3. **Two editions.** The collaborator edition has no paths, request IDs,
   titles, names or Exploration view, and the researcher reviews it before
   sharing.
4. **First run: ask for the lab's description and the PI's details** (name,
   institutions, ORCID) in the researcher's own words.
5. **Publications are the lab's own work**, fetched from PubMed each run: PI
   first or last author, lab institution, no essays or preprint duplicates,
   always with DOI links.
6. **Nothing is published.** Outputs stay local in `output/`.
