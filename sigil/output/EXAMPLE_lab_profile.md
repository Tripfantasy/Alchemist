# Example Lab

⚠️ **Synthetic example.** Built by running sigil on forage's mock collection (`forage/scripts/make_mock_inventory.py`). Every figure is a genuine output of that run, but the lab, its description, files, request IDs and names are fabricated. It shows the format; it describes no real lab.

**Lab overview** · Built 2026-11-04

> We study how the heart and other organs repair themselves after injury, from
> the molecular programs that switch on in regenerating cells to the tissue
> architecture they rebuild. Most of our work pairs single-cell and spatial
> genomics with physiology and imaging in mouse injury models.

Cardiac regeneration is the lab's largest theme, followed by disease modeling,
tissue architecture and gene regulation. Most questions are answered with bulk
or single-cell RNA-seq, and much of the work is timed after an injury or
treatment.

**At a glance:** 5 research themes · 40 sequencing projects · 15 project
folders of data · 13 methods in use

A *project folder* is one directory of related work in the lab's data
collection; counts use folders, not files, because one instrument can write
thousands of files for a single session.

---

## 1. Research themes

| Theme | Projects | Main approaches |
| --- | --- | --- |
| Cardiac regeneration | 13 | Bulk RNA-seq (6), single-cell RNA-seq (5), DNA-seq (1), spatial (1) |
| Disease modeling | 9 | DNA-seq (3), bulk (2), single-cell (2), chromatin accessibility (1), multiome (1) |
| Tissue architecture | 7 | Single-cell RNA-seq (3), bulk (3), spatial (1) |
| Gene regulation | 7 | Bulk RNA-seq (4), single-cell RNA-seq (3) |
| Development | 4 | Bulk RNA-seq (2), single-cell (1), DNA-seq (1) |

- **Cardiac regeneration** is a third of all projects, split between bulk and
  single-cell RNA-seq, with one spatial run.
- **Disease modeling** is the most varied: the only theme led by DNA
  sequencing, and the only one with chromatin accessibility and multiome data.
- **Tissue architecture** leans on single-cell RNA-seq and is one of two themes
  with spatial transcriptomics.

## 2. Methods beyond sequencing

Seven other methods each appear in one or two project folders:

- **Spatial transcriptomics** on kidney and lung
- **Patch-clamp electrophysiology** on cardiomyocytes, and **calcium imaging** in cortex
- **Confocal microscopy** of the heart and left ventricle, and **in situ hybridization** on kidney
- **Proteomics** on liver, and **behavior**

## 3. Biological focus

- **Tissues:** left ventricle, cardiomyocytes, kidney and liver (2 folders
  each), then heart, lung and cortex (1 each).
- **Stages and timepoints:** mostly time after injury or treatment (left
  ventricle 2, kidney 2, heart 1); one neonatal (lung) and two adult (liver,
  cortex) folders.
- **Conditions and models:** myocardial infarction (2), injury (2),
  high-fat diet (1).

## 4. Toolkit

- **Genetic tools:** a CreERT2 driver, a tdTomato reporter and a GCaMP
  indicator.
- **Analysis languages:** Python (3 folders), R (2), MATLAB (1).

## 5. Finding data

- Ask forage first: `/forage <what you are looking for>`, or add `--quick` for
  a file list.
- Physiology and behavior data sit under `/rigs/`; imaging under
  `/core_imaging/`; sequencing under `/lab_data/sequencing/`.

## 6. Exploration

forage, the lab's data-discovery assistant, has catalogued 169 files (286 GB)
across 19 folders. No archives have been found yet, and no questions have been
logged against this collection.

## Appendix

- Unmapped terms: none.
- Files: `EXAMPLE_dashboard.html` (interactive charts).

---

*Built by sigil from the lab's data collection. Regenerate rather than edit:
the numbers come from the data files.*
