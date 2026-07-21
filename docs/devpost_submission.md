# Devpost submission copy

Replace only the three bracketed placeholders after deployment, video upload,
and `/feedback` collection. Keep all submitted materials in English.

## Project title

ResistSense — A Genome Firewall for AMR Evidence

## Tagline

Predict resistance. Challenge the evidence. Abstain when confidence becomes risk.

## Short description

ResistSense is a safety-first antimicrobial-resistance research workflow for
*Escherichia coli*. It analyzes an assembled bacterial FASTA, separates known
biological evidence from calibrated statistical associations, applies six
independent safety barriers, and returns a resistance-associated signal, a
susceptibility-compatible signal, or an explicit no-call. GPT-5.6 Sol audits
the locked scientific report for contradictions and unsafe communication
without receiving raw DNA or changing any result.

## 1. Problem and challenge

Antimicrobial-resistance predictors often compress uncertainty into a binary
answer. This becomes risky when a genome has poor quality, lies outside the
training distribution, lacks an annotated molecular target, produces model
disagreement, or contains conflicting evidence. A high probability alone does
not establish that an antibiotic will work. ResistSense addresses this gap by
making abstention, evidence provenance, and residual error visible throughout
the workflow.

## 2. Target audience

The primary users are microbial-genomics researchers, public-health and
surveillance teams, laboratory scientists, and model auditors evaluating AMR
decision-support systems. ResistSense is a research prototype, not a
diagnostic device. It does not prescribe or rank treatments, and every emitted
assessment requires confirmation through standard laboratory antimicrobial-
susceptibility testing.

## 3. Solution and core features

Users upload an assembled *E. coli* FASTA or load a verified held-out example.
The backend performs sequence quality control, AMRFinderPlus annotation,
independent target checks, calibrated per-antibiotic prediction, OOD detection,
conformal uncertainty analysis, and deterministic firewall evaluation.

The product includes:

- three safe outcomes: resistance-associated signal,
  susceptibility-compatible signal, and no-call;
- Firewall Replay separating statistical, biological, and safety evidence;
- Prediction Autopsy showing prevented and residual held-out errors;
- class-aware coverage and risk reporting;
- a human-review worklist and laboratory handoff;
- an Evidence Passport with model, policy, runtime, and split provenance;
- a 12-case executable adversarial safety evaluation; and
- a GPT-5.6 evidence-conflict audit protected by deterministic validation.

## 4. Unique selling proposition

Most AMR demos optimize the prediction and explain it afterward. ResistSense
can refuse the prediction before explanation. It never converts missing
markers into susceptibility, keeps biological evidence distinct from model
association, blocks genetically related train/test leakage, and exposes errors
that escape the firewall. GPT-5.6 is deliberately downstream: it cannot modify
status, probability, evidence, or safety policy, and raw genomic sequence never
leaves the scientific backend.

## 5. Implementation and technology

The cohort contains 2,909 quality-controlled *E. coli* assemblies with five
laboratory-derived antibiotic labels and 1,306 frozen cgMLST groups. Related
genomes never cross training, probability-calibration, conformal-calibration,
or test partitions. Four endpoints use the challenge-recommended regularized
AMRFinderPlus logistic baseline; ciprofloxacin uses a training-selected
transparent ensemble with strand-invariant hashed k-mers.

The backend uses Python, FastAPI, scikit-learn, AMRFinderPlus, conformal
prediction, OOD detection, and deterministic safety policies. The frontend
uses React, TypeScript, vinext, CSS, and Three.js. GPT-5.6 Sol runs through the
Responses API with Structured Outputs, an allowlisted input contract, `store`
disabled, and a second deterministic validator. Deployment uses Docker,
Google Cloud Build, Artifact Registry, Secret Manager, Nginx, and Cloud Run.

## 6. Results and impact

The frozen grouped test includes 437 genomes from 198 unseen genetic groups.
All five endpoints exceed 94% empirical conformal coverage at the declared 95%
target. Prediction Autopsy identifies 68 base-model errors: the firewall blocks
55 and exposes the 13 residual emitted errors. Cefotaxime reaches 69.6%
firewall coverage while preserving 99.7% selective accuracy after adding a
drug-specific independent evidence gate. The complete research release passes
47 machine-readable gates, 58 backend tests, frontend lint/build/tests, and an
adversarial model-output safety suite.

These are internal grouped-validation results. Independent external and
clinical validation remain future work and are not claimed.

## What was your most fun moment during the hackathon?

The most satisfying moment was intentionally giving GPT-5.6 a result it was
not allowed to change and watching the deterministic firewall reject a
non-compliant output while preserving the scientific report. It turned a
failure into the clearest demonstration of the product idea: useful AI should
be able to say “I cannot safely validate this” without hiding uncertainty or
overriding evidence.

## Additional information

I am the sole participant and project owner. The dataset curation, scientific
scope, model strategy, safety boundaries, product decisions, and submission
claims are mine. Codex was used as a software-development tool for repository
inspection, implementation, testing, documentation, deployment preparation,
and review; it is not a team member or coauthor.

Work completed before Build Week and work added during the event are separated
in `docs/build_week_submission.md`. The repository includes Apache-2.0
licensing, third-party notices, reproducible evaluation artifacts, and clear
research-only limitations.

## Testing instructions

1. Open `[PERMANENT_CLOUD_RUN_URL]` in a desktop browser.
2. Click `Start 90-second judge tour`.
3. Load the verified frozen-test case; no upload or account is required.
4. Inspect the five antibiotic assessments and select different results to see
   mechanism-informed illustrations.
5. Open Firewall Replay, Prediction Autopsy, the GPT-5.6 audit, the adversarial
   guardrail suite, and the Evidence Passport.
6. Download the JSON report and verify that scientific output and the optional
   language-model audit remain separate.

The demo is free and requires no credentials. Results are provisional genomic
evidence and require laboratory confirmation.

## URLs

- Live project: `[PERMANENT_CLOUD_RUN_URL]`
- GitHub: `https://github.com/arkhangio10/resistsense`
- YouTube: `[PUBLIC_YOUTUBE_URL]`
- Codex `/feedback` Session ID: `[CODEX_SESSION_ID]`

## Technologies and tags

React, TypeScript, Python, FastAPI, scikit-learn, AMRFinderPlus, BV-BRC,
OpenAI GPT-5.6 Sol, OpenAI Responses API, Structured Outputs, Codex, Three.js,
Docker, Google Cloud Build, Secret Manager, Google Cloud Run, Bioinformatics,
Genomics, Antimicrobial Resistance, Responsible AI, Uncertainty Quantification.
