# Accession & Repository Reference

Lookup facts only. The *procedure* — probing, the format ladder, sample mapping,
loader conventions, the trap list — lives in `workflows/etl_geo.md`.

## Accession patterns

| Pattern | Repository | Level | Holds |
| --- | --- | --- | --- |
| `GSE######` | GEO | Series | One study; supplementary processed files |
| `GSM######` | GEO | Sample | One library/sample |
| `GPL#####` | GEO | Platform | Instrument + organism |
| `GDS####` | GEO | DataSet | Curated legacy; mostly microarray |
| `SRP######` | SRA | Study | Raw reads |
| `SRR######` | SRA | Run | One sequencing run |
| `SRX######` | SRA | Experiment | Library, ≥1 run |
| `PRJNA######` | BioProject | Project | Umbrella; links GEO + SRA |
| `SAMN########` | BioSample | Sample | Biological source metadata |
| `E-MTAB-####` | ArrayExpress / BioStudies | Study | EU equivalent of GEO |
| `phs######` | dbGaP | Study | **Controlled access** — human, DUA required |
| `EGAS########` | EGA | Study | **Controlled access** — EU human |
| `syn########` | Synapse | Any | Registration + often a DUA |
| `PXD######` | PRIDE | Project | Proteomics |
| `EMPIAR-#####` | EMPIAR | Entry | EM raw images |
| `10.5281/zenodo.######` | Zenodo | Deposit | Anything; often frozen analysis objects |

**A GEO SuperSeries lists sub-series and holds no files of its own.** Probe the
sub-series. Conversely a `GSE` may be listed under a `PRJNA` that also carries
the raw `SRP` — the same study, three accessions.

## URL patterns

Series page and machine-readable metadata:

```
https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE214435
https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE214435&targ=self&form=text&view=brief
```

Supplementary file directory (this is where processed matrices live):

```
https://ftp.ncbi.nlm.nih.gov/geo/series/GSE214nnn/GSE214435/suppl/
```

The `nnn` grouping is the accession with its last three digits replaced by
`nnn`. Samples follow the same shape under `/geo/samples/GSM661nnn/GSM6612345/suppl/`.

E-utilities (used by `scripts/geo_probe.py`):

```
.../esearch.fcgi?db=gds&term=GSE214435[ACCN]
.../esummary.fcgi?db=gds&id=<uid>&retmode=json
.../elink.fcgi?dbfrom=gds&db=sra&id=<uid>       # GEO -> SRA link
```

Etiquette: ≤3 requests/second unregistered. `geo_probe.py` throttles; don't
loop over accessions in a shell with `curl`.

ENA — better than SRA for raw reads, serves FASTQ over plain HTTPS:

```
https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJNA######&result=read_run&fields=run_accession,fastq_ftp,fastq_bytes
```

## What each repository actually serves

- **GEO** — processed files are author-uploaded and *unvalidated*: naming,
  format, and completeness are whatever the submitter chose. Expect anything.
- **SRA** — raw reads only, no processed data, ever.
- **ENA** — mirrors SRA with direct FASTQ URLs. Prefer it.
- **ArrayExpress/BioStudies** — like GEO; less common in US neuroscience papers.
- **Zenodo/figshare** — where the intermediate objects a GitHub repo can't hold
  end up (>100 MB `.h5ad`, `.rds`). Often the fastest route to Tier 1.
- **dbGaP / EGA** — controlled access. Weeks-to-months application through an
  institutional signing official. If the target analysis needs these, the
  reproduction is **blocked**; report the route, don't route around it.
- **Synapse** — common for consortium neuroscience data (AMP-AD, PsychENCODE).
  Registration, sometimes a DUA. `synapseclient`.
- **CELLxGENE / HCA / Allen Brain Map / UCSC Cell Browser / Single Cell Portal**
  — curated `.h5ad`/browsers of published data. Cleaner than the original
  deposit, but **re-curated**: annotations and filtering may not be the paper's.
  Say so if you use one.

## Naming conventions in the wild

What a GEO `suppl/` listing tends to look like, and what it implies:

| Filename shape | Means |
| --- | --- |
| `GSM..._<label>_filtered_feature_bc_matrix.h5` | Tier 2, per sample. Best case. |
| `GSM..._<label>_barcodes/features/matrix.*.gz` | Tier 3 triplet; needs per-sample directories, prefixes stripped |
| `GSE..._raw_counts.csv.gz` | Tier 4 merged table. Check whether it's raw or normalized |
| `GSE..._processed.h5ad` / `_seurat.rds` | Tier 1 — authors' own object, with their annotations |
| `GSE..._RAW.tar` | Series-level bundle of all samples; extract first. The real download cost |
| `..._peaks.*`, `..._fragments.tsv.gz` | ATAC/Multiome, not RNA |
| `..._TPM`/`_FPKM`/`_normalized` in the name | **Not** valid input to DESeq2/edgeR |

## Organism reference builds

Match the paper's build, not the current one.

| Organism | Common builds | Note |
| --- | --- | --- |
| Mouse | `mm10` (GRCm38), `GRCm39` | The 2020 shift; coordinates and some gene models differ |
| Human | `hg19`/GRCh37, `GRCh38` | 10x `GRCh38-2020-A` is a specific filtered variant |
| Rat | `Rnor_6.0`, `mRatBN7.2` | Annotation quality differs substantially |
| Zebrafish | `GRCz11` | |

Gene symbols follow the organism's nomenclature: mouse `Gfap`, human `GFAP`. A
case-insensitive match that papers over a species mix-up is worse than an error.
