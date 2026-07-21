# ResistSense execution status

Status date: 2026-07-21. This is an evidence ledger, not a claim of clinical or
external validity.

## Outcome

The code path from an uploaded FASTA to a safety-audited result is executable.
It fails closed: missing FASTA quality, AMRFinderPlus, model, calibration, OOD,
conformal, or independent target evidence produces `no_call`. The React
application only renders backend results and never generates probabilities.

The project is **internally evaluable but not externally validated**. The
organizers' clarification permits a self-curated dataset; the 2,909-genome,
1,306-group cohort is frozen, fully annotated, and trained. The frozen grouped
test contains 437 genomes from 198 groups. Model selection uses training groups
only. A uniform conformal alpha of 0.05 gives empirical coverage from 94.1% to
99.1%. Cefotaxime's drug-specific AMRFinderPlus subclass gate raises firewall
coverage from zero to 69.6% while preserving 99.7% selective accuracy.

## Requirement ledger

| Challenge / plan requirement | Status | Evidence |
|---|---|---|
| One species | Complete | *E. coli*, taxon 562, frozen in `configs/resistsense.yaml` |
| Three to five antibiotics | Complete | Five endpoints selected from laboratory-only audit |
| Reconstructed FASTA input | Complete in code | Parser, checksum, length/contig/ambiguity QC and upload contract |
| Laboratory phenotypes | Complete and frozen | 33,614 laboratory records audited; 2,909 genomes retain all five clear labels and pass metadata QC |
| Genetic-group split | Complete | 1,306 cgMLST HC50 groups frozen across train, probability calibration, conformal calibration, and test; no group crosses partitions |
| Reproducible FASTA acquisition | Complete | 2,909 cohort FASTAs are checksum-frozen and pass sequence QC |
| AMRFinderPlus | Complete | Official NCBI image pinned by digest; all 2,909 cohort genomes annotated without extraction failures |
| Known-gene/mutation features | Complete in code | AMRFinderPlus features and evidence schema |
| k-mer branch | Complete in code | Strand-invariant hashed k-mers with fixed vocabulary |
| Genomic/protein embeddings | Experiment deferred | No unsupported deep model is shipped; the existing k-mer branch is separately ablated against the marker baseline |
| Logistic expert | Complete in code | Per-antibiotic balanced logistic regression |
| Boosting expert | Complete in code | Per-antibiotic histogram gradient boosting |
| Transparent ensemble | Complete and selected only where supported | Training-group cross-validation selects the full soft-vote ensemble for ciprofloxacin; four endpoints retain the recommended marker logistic baseline |
| Separate calibration | Complete in code | Probability calibration and conformal calibration use disjoint genetic groups |
| OOD detection | Complete in code | Nearest-neighbor distance ranked against conformal groups |
| Conformal prediction | Complete and release-gated | Uniform alpha 0.05; all endpoints exceed the 90% release minimum on the frozen grouped test |
| Model disagreement | Complete in code | Max-min expert probability gate |
| Molecular target gate | Complete | Independent BLAST alignment succeeded for all 437 frozen-test genomes; AMR-marker absence is never accepted as target evidence |
| Evidence levels A-E | Complete | Structured result contract and deterministic explanations |
| Communication auditor | Deterministic safety auditor complete | Blocks treatment language, changed numbers, and missing lab confirmation |
| OpenAI second-pass auditor | Complete and live-verified locally | GPT-5.6 Sol Responses API Structured Output, strict validator, privacy allowlist, request/response and aggregate-token telemetry, deterministic fallback, and adversarial tests are complete. A credentialed 2026-07-21 verification returned a validated `source=openai` audit with 2,819 aggregate tokens and zero raw FASTA bases sent. |
| React application | Complete | Upload, QC, safe result labels, six barriers, class-aware coverage, Prediction Autopsy, constrained GPT audit, verified judge example, and downloadable JSON |
| Container deployment | Cloud Run configuration complete; external deployment pending | Single same-origin container, Secret Manager binding, bounded scaling, health check, and PowerShell deployment workflow are implemented |
| Epidemiology | Partial | Aggregate phenotype/QC dashboard only; geography/time await permitted metadata |
| Prediction Autopsy | Complete | Nine deterministic frozen-test cases summarize 55 prevented and 13 residual emitted errors; API and React presentation are implemented |
| Standard metrics | Complete and executed | Balanced accuracy, class recall, precision/F1, AUROC, PR-AUC, Brier, reliability, and 1,000-replicate group-bootstrap intervals |
| Firewall metrics | Complete and executed | Unsafe confidence, errors prevented, selective accuracy, coverage, risk-coverage, worst group, OOD failure, explanation concordance |
| Class-aware safety report | Complete and executed | Exact R/S coverage numerators and denominators, harm-specific residuals, class-aware risk/coverage curves, and 1,000-replicate genetic-group bootstrap intervals |
| Final trained models and demo cases | Complete internally | Five artifacts share the frozen feature hash; `release_gate.json` passes every configured strategy, hash, target, coverage, and selective-accuracy check |

## Completion gate

The following sequence produces a scientifically evaluable release:

1. Archive the organizers' dataset-policy clarification with the submission.
2. Complete and re-freeze the 2,909 FASTA files with checksums and sequence QC.
3. Retain the already pinned NCBI AMRFinderPlus image/database digest.
4. Retain the checksum-frozen NCBI target references and independent annotator.
5. Extract features and freeze their checksum.
6. Train only on the frozen training and calibration partitions.
7. Export predictions for the frozen grouped test and run the full suite.
8. Keep k-mers, embeddings, or any advanced branch only when grouped testing
   demonstrates a useful accuracy or safety gain.
9. Populate Prediction Autopsy from genuine held-out errors and deploy the API
   and React client together.

Gates 1-8 are complete. The predeclared training-group rule selects the
advanced branch only for ciprofloxacin. The Prediction Autopsy and joint
API/React implementation in gate 9 and the Build Week safety/OpenAI layers are
complete locally. Credentialed GPT-5.6 verification passed; external Cloud Run
deployment remains pending.

Any runtime missing models, AMRFinderPlus, calibration, target annotation, or
quality evidence fails closed to `no_call`. External validation remains an
explicit limitation even when the local release gate passes.

## Final local verification

- Backend: 58 tests pass.
- Frontend: production build, two rendered-output tests, and ESLint pass.
- Release validator: `research_demo_status=pass`, while
  `clinical_release_status=fail_not_externally_validated` remains enforced.
- Packaged frozen assets: 8,454,922 bytes; SHA-256
  `b285e3c5c009a9df9f23d10dd8ac01ab2eb5be68acbaed050322bdbb23db255c`.
- Real FASTA smoke test: a 5.09 Mb, 69-contig *E. coli* assembly passed sequence
  QC. Because the host session lacks an AMRFinderPlus executable or running
  Docker daemon, every endpoint correctly returned `no_call` with explicit
  machine-readable reasons instead of inferring susceptibility.
- Verified frozen-test example: the API returns the real held-out sample
  `562.100025`. The missing-key fallback remains covered by tests. During live
  credentialed verification, one model output was rejected without changing
  the scientific report, and a subsequent structured audit passed every
  deterministic validation rule using `gpt-5.6-sol`.

The remaining deployment checks require authorized Google Cloud billing and a
server-side OpenAI secret. They are not local code defects and have not been
represented as complete.
