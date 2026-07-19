# ResistSense - Phase 2 data audit

Status: **self-curated candidate cohort and partitions frozen**. The organizers clarified
that teams may build and debug their own dataset. The clarification message or
URL must be archived with the submission because it supersedes the original
brief's reference to an organizer-provided dataset.

## Decision

- Supported species: **Escherichia coli** (NCBI taxon 562).
- AMRFinderPlus organism mode: **Escherichia**.
- Selected antibiotics: ampicillin, ciprofloxacin, cefotaxime, gentamicin, and
  trimethoprim/sulfamethoxazole.
- Training labels: only `Resistant` and `Susceptible` records whose BV-BRC
  `evidence` is exactly `Laboratory Method`.
- Intermediate labels are not used in the binary audit.
- A genome/antibiotic pair with both R and S observations is excluded.

## Why the challenge warning changes the dataset

The broad E. coli query initially returned 479,634 R/S records for the five
first candidates. Of these, 445,844 were tagged `Computational Method` and only
33,031 were tagged `Laboratory Method`. Using the broad phenotype field would
therefore have trained ResistSense mostly on predictions produced by another
model instead of laboratory outcomes.

The final query applies the laboratory-evidence filter before any balance or
sample-size calculation. This is the most important result of the audit.

## Source hierarchy

1. BV-BRC `genome_amr` records with `evidence=Laboratory Method`.
2. BV-BRC genome metadata and FASTA files linked by `genome_id`.
3. AMRFinderPlus for model features, genes, and curated point mutations.
4. ResFinder or cAMRah only as secondary concordance checks, never as phenotype
   labels.
5. Kaggle mirrors only for tutorials; they are not accepted as provenance.

Official references:

- https://www.bv-brc.org/docs/quick_references/organisms_taxon/amr_phenotypes.html
- https://www.bv-brc.org/docs/quick_references/ftp.html
- https://github.com/ncbi/amr
- https://www.ncbi.nlm.nih.gov/pathogens/pathogens_help/

## Species screen

The global laboratory-only screen returned 683,461 R/S records. The leading
taxa were M. tuberculosis (100,080 records), E. coli (92,452), S. pneumoniae
(90,538), K. pneumoniae (66,140), S. enterica (55,019), and S. aureus
(41,458). These are record counts, not deduplicated isolates.

E. coli was selected because it combines:

- 8,711 unique genomes across the selected endpoints;
- high class support after deduplication;
- acquired genes and organism-specific point mutations;
- explicit AMRFinderPlus support through the `Escherichia` organism mode;
- 3,633 observed cgMLST HC50 clusters among 8,461 cluster-annotated genomes;
- no dominant HC50 cluster larger than 724 genomes;
- 98.92% preliminary genome-QC retention.

M. tuberculosis has slightly more laboratory records, but requires a more
specialized drug-susceptibility and mutation interpretation workflow and is a
weaker match for the challenge's default AMRFinderPlus-centered baseline.

## Final phenotype matrix

Counts below use unique genome/antibiotic pairs after removing conflicting
labels. The QC columns additionally require preliminary assembly quality.

| Antibiotic | Eligible pairs | Susceptible | Resistant | R % | QC pairs | QC S | QC R |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ampicillin | 6,490 | 2,831 | 3,659 | 56.38 | 6,397 | 2,814 | 3,583 |
| Ciprofloxacin | 7,307 | 5,461 | 1,846 | 25.26 | 7,242 | 5,418 | 1,824 |
| Cefotaxime | 6,585 | 5,317 | 1,268 | 19.26 | 6,531 | 5,293 | 1,238 |
| Gentamicin | 7,340 | 6,478 | 862 | 11.74 | 7,280 | 6,426 | 854 |
| Trimethoprim/sulfamethoxazole | 4,140 | 2,704 | 1,436 | 34.69 | 4,102 | 2,691 | 1,411 |

Meropenem was rejected as a training endpoint: after laboratory-only filtering
and pair deduplication, it had 5,796 eligible pairs but only 69 resistant
isolates (1.19%). It may be retained as a stress-test/no-call demonstration,
but not as one of the five primary models. Tigecycline was also rejected after
the initial screen found only 10 resistant laboratory records.

## Duplicate and conflict audit

- Ampicillin: 205 repeated records and 7 conflicting pairs.
- Ciprofloxacin: 1,300 repeated records and 18 conflicting pairs.
- Cefotaxime: 1 repeated record and no conflicts.
- Gentamicin: 219 repeated records and no conflicts.
- Trimethoprim/sulfamethoxazole: 2 repeated records and no conflicts.

Repeated concordant records collapse to one pair. Conflicting pairs are
excluded rather than resolved by majority vote, because they may reflect
method, breakpoint, or temporal differences.

## Phenotype metadata quality

Raw MIC/diameter values are incomplete: 9.56% for ampicillin, 32.46% for
ciprofloxacin, 19.03% for cefotaxime, 22.90% for gentamicin, and 13.83% for
trimethoprim/sulfamethoxazole. The model should therefore use the pinned R/S
label instead of attempting to reconstruct every label from MIC.

Testing-standard coverage ranges from 54.64% to 73.89%. Values such as
`EUCAST`/`eucast` and `CLSI`/`clsi` must be normalized, but records from
different standards must remain traceable for subgroup evaluation.

## Genome quality and diversity

All 8,711 selected genome IDs matched a BV-BRC genome record.

- 8,663 are marked Good, 42 Poor, and 6 Unknown.
- 8,617 genomes (98.92%) pass the preliminary QC policy.
- Median genome length: 5,091,254 bp.
- Median contigs: 116; 95th percentile: 257.
- Median contig N50: 192,548 bp.
- Median CheckM completeness: 99.78%.
- CheckM contamination is available for 3,183 genomes; median 0.2%.
- cgMLST HC50 is available for 8,461 genomes and contains 3,633 distinct
  clusters; the largest contains 724 genomes (8.56% of cluster-annotated data).

Only 5.5% expose an assembly accession in the downloaded metadata. This does
not prove that FASTA is missing because BV-BRC also serves sequences directly
by `genome_id`, but FASTA availability must be verified before the final master
dataset is frozen.

## Selected endpoint roles

- **Ampicillin:** strong, relatively balanced acquired beta-lactam resistance
  endpoint and interpretable biological baseline.
- **Ciprofloxacin:** chromosomal mutations plus acquired mechanisms; primary
  test of mutation-aware and multimodal modelling.
- **Cefotaxime:** extended-spectrum beta-lactamases/AmpC and a more difficult
  beta-lactam endpoint than ampicillin.
- **Gentamicin:** deliberately imbalanced endpoint for PR-AUC, calibration,
  conformal prediction, and no-call evaluation.
- **Trimethoprim/sulfamethoxazole:** dual-target combination with useful class
  balance and distinct resistance families.

## Frozen cohort decision

The candidate cohort requires all five non-contradictory laboratory labels,
preliminary assembly quality, and a non-empty BV-BRC cgMLST HC50 group. It
contains 2,909 genomes across 1,306 genetic groups. Entire groups are assigned
deterministically to four partitions:

- train: 1,745 genomes;
- probability calibration: 436 genomes;
- conformal calibration/OOD: 291 genomes;
- held-out test: 437 genomes.

The final freeze occurs only after every FASTA is downloaded, checksumed, and
passes sequence QC. Any failure is excluded and the deterministic grouped
partition is rebuilt before model development.

## Reproducibility

- Selection configuration: `configs/phase2_selection.yaml`.
- Audit implementation: `scripts/audit_phase2.py`.
- End-to-end downloader: `scripts/run_phase2.ps1`.
- Frozen cohort builder: `scripts/curate_dataset.py`.
- Frozen manifest and exclusions: `data/processed/curated/`.
- Machine-readable audit: `artifacts/phase2/phase2_audit.json`.
- Final matrix: `artifacts/phase2/ecoli_antibiotic_matrix.csv`.
- Source data are ignored by Git and retained under `data/raw/bvbrc/`.
