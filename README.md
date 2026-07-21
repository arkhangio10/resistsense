# ResistSense

**ResistSense - A Genome Firewall for Antimicrobial Resistance**

ResistSense is a defensive research prototype that turns a reconstructed,
quality-checked *Escherichia coli* FASTA into one of three results for each
supported antibiotic:

- resistance signal;
- susceptibility-compatible signal;
- no-call — insufficient or conflicting evidence.

It is not a diagnostic device and never recommends treatment. Every result
must be confirmed with standard laboratory testing.

## Live demo

The permanent public demo is available at
[`https://resistsense-54azg7trza-uc.a.run.app`](https://resistsense-54azg7trza-uc.a.run.app).
It runs on Google Cloud Run independently of the development laptop. A
project-scoped monthly budget alerts at approximately USD 5 and automatically
closes public ingress at approximately USD 10; the interface reports only a
deduplicated anonymous-browser count.

OpenAI usage is protected separately: the `gpt-5.6-sol` project alerts at 80%
of its USD 5 monthly threshold, while the application atomically reserves and
settles each audit against a USD 5 Firestore ledger. Each anonymous browser is
limited to three audits per UTC day. Reaching either limit, losing quota
storage, or exceeding the allowlisted payload size prevents the OpenAI request
and returns the unchanged deterministic scientific report.

## Current status

The BV-BRC laboratory-phenotype audit is reproducible. The 2,909-genome frozen
cohort has been downloaded, QC-checked, annotated with AMRFinderPlus, and used
to train five grouped and calibrated model artifacts. The frozen 437-genome
test split has independent target annotations and a machine-readable internal
validation report with genetic-group bootstrap intervals. A training-group-only
selection rule retains the full ensemble for ciprofloxacin and the recommended
AMRFinder logistic baseline for the other four endpoints. Cefotaxime now uses
drug-specific AMRFinderPlus subclass evidence and has 69.6% firewall coverage
instead of zero. All endpoints exceed 94% empirical conformal coverage under a
uniform 95% target. FASTA safety gates, OOD detection, the confidence firewall,
FastAPI service, and React frontend are implemented and tested. External
validation remains open. Prediction Autopsy exposes frozen-test errors,
including residual errors that escaped the firewall; see
`docs/model_validation.md` and `docs/prediction_autopsy.md`.

The Build Week layer adds an exact class-aware safety report and a constrained
GPT-5.6 Evidence Conflict Auditor. GPT receives only allowlisted structured
evidence, never raw FASTA, original filenames, checksums, free-form user text,
secrets, or personal data. It cannot change scientific results. If OpenAI is
unavailable or its output fails validation, the deterministic report is
returned unchanged.

The judge-facing application now turns those controls into an auditable review
workflow:

- a 90-second guided Judge Mode using a frozen, traceable test case;
- Firewall Replay, which keeps statistical association, known biological
  evidence, safety triggers, and the final assessment visibly separate;
- an antibiotic-specific, mechanism-informed 3D illustration that distinguishes
  beta-lactam envelope failure, ciprofloxacin-associated DNA stress,
  gentamicin-associated translation and membrane stress, and sequential folate
  blockade; no-call remains visually neutral;
- a human-review worklist that prioritizes no-calls without ranking therapies;
- an executable 12-case adversarial suite around the GPT-5.6 boundary;
- a fail-closed USD 5 OpenAI usage guard with per-browser daily limits;
- an Evidence Passport containing sample, toolchain, policy, model, privacy,
  and frozen-split provenance; and
- an exportable JSON evidence packet for reproducible handoff.

The adversarial suite tests deterministic enforcement around the optional
model response; it is not biological or clinical validation. Independent
external validation remains explicitly incomplete.

## Architecture

```text
React frontend
      |
FastAPI contract
      |
FASTA validation -> AMRFinderPlus + k-mers -> per-drug ensemble
      |                        |                  |
      |              independent target gate    |
      +-------------- confidence firewall <-----+
                           |
 resistance signal / susceptibility-compatible signal / no-call
                           |
              optional GPT-5.6 evidence audit
              (structured, non-authoritative)
```

The React frontend only presents results. All scientific computation and
safety policy live in the Python backend.

## Quick start

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn resistsense.api:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Configure `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` for local development.
Set `OPENAI_API_KEY` only in the backend environment to enable the optional
evidence audit. The scientific pipeline works without it.

## Verified container demo

The API image contains the pinned AMRFinderPlus database and local BLAST
binaries, so it does not need a Docker socket at runtime.

```powershell
docker compose build
docker compose up -d
```

Open `http://localhost:3000`. The API health endpoint is
`http://localhost:8000/health`. See `docs/deployment.md` for public-origin and
release-asset configuration.

## Permanent Google Cloud deployment

The repository includes a single-container Cloud Run deployment that combines
the React application, FastAPI service, pinned AMRFinderPlus runtime, local
models, evaluation artifacts, and same-origin proxy. It scales to zero and caps
concurrency and maximum instances. See
[`docs/google_cloud_run_deployment.md`](docs/google_cloud_run_deployment.md).

## Verified phase-2 audit

```powershell
python scripts\audit_phase2.py `
  --input data\raw\bvbrc\ecoli_phase2_selected_lab.tsv `
  --genome-metadata data\raw\bvbrc\ecoli_genome_quality.tsv `
  --output-dir artifacts\phase2
```

The audit uses only `Laboratory Method` records, collapses repeated
genome-antibiotic observations, excludes R/S conflicts, and applies preliminary
assembly-quality policy.

## Reproducible execution stages

```powershell
# 1. Build the frozen laboratory-only cohort and grouped partitions
python scripts\curate_dataset.py

# 2. Preview or download the frozen cohort from the official BV-BRC API
python scripts\download_fastas.py `
  --manifest data\processed\curated\dataset_manifest.jsonl --limit 0
python scripts\download_fastas.py `
  --manifest data\processed\curated\dataset_manifest.jsonl `
  --limit 0 --workers 4 --execute

# 3. Re-freeze checksums after download, then extract AMR + k-mer features
python scripts\curate_dataset.py
python scripts\extract_features.py `
  --manifest data\processed\curated\dataset_manifest.jsonl

# Run one FASTA through the complete fail-closed report pipeline
python scripts\analyze_fasta.py data\raw\fasta\562.100000.fna

# 4. Train with the frozen train/calibration/conformal/test group split
python scripts\select_model_strategy.py
python scripts\train_baselines.py `
  --features data\processed\features\resistsense_features.csv

# 5. Export and evaluate frozen grouped-test predictions
python scripts\export_test_predictions.py --target-workers 16
python scripts\evaluate_predictions.py `
  --predictions artifacts\evaluation\predictions.csv `
  --bootstrap-replicates 1000

# Compare the full branch with the challenge-recommended AMRFinder baseline
python scripts\evaluate_feature_ablation.py --bootstrap-replicates 1000

# Build deterministic held-out error cases for the API and React application
python scripts\build_prediction_autopsy.py

# Build exact class-aware metrics and the judge-facing Markdown summary
python scripts\build_class_aware_safety_report.py --bootstrap-replicates 1000

# Refuse release when hashes, strategies, coverage, or safety gates disagree
python scripts\validate_release.py
```

The final training command deliberately refuses an unfrozen split unless the
explicit development-only override is supplied.

## Supported scope

- Species: *Escherichia coli* (NCBI taxon 562).
- Antibiotics: ampicillin, ciprofloxacin, cefotaxime, gentamicin, and
  trimethoprim/sulfamethoxazole.
- Input: one reconstructed FASTA genome.
- Out of scope: sample collection, sequencing, assembly, species
  identification, treatment selection, and organism modification.

## Required external components

- Self-curated BV-BRC laboratory cohort with frozen cgMLST-grouped partitions.
- FASTA assemblies with frozen checksums and passing assembly QC.
- AMRFinderPlus and its pinned database. A pinned official `ncbi/amr` Docker
  image is the automatic fallback when no local executable is installed.
- The included independent target aligner and checksum-frozen NCBI K-12
  references under `configs/target_references/`.
- A trained and calibrated artifact for every declared antibiotic.

When any required component is missing, the runtime returns `no-call`.

See `docs/execution_status.md` for the requirement-by-requirement status.

## Build Week disclosure

Work completed before this iteration and work added during Build Week are
separated in [`docs/build_week_submission.md`](docs/build_week_submission.md).
Abel Mancilla is the sole owner and team member. Codex was used as a
software-development tool; it is not an author, coauthor, or team member.

## License

ResistSense is available under the Apache License 2.0. See `LICENSE` and
`THIRD_PARTY_NOTICES.md`.
