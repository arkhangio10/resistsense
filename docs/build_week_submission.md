# OpenAI Build Week submission evidence

## Work completed before this Build Week iteration

- BV-BRC laboratory-only cohort curation and conflict removal.
- Frozen cgMLST-grouped train/calibration/conformal/test partitions.
- AMRFinderPlus and hashed k-mer feature extraction.
- Five calibrated per-antibiotic models and confidence firewall.
- Independent target gate, OOD gate, conformal abstention, FastAPI service, React interface, and Prediction Autopsy.

## Work added for this Build Week iteration

- Class-aware safety report with exact numerators/denominators, group bootstrap intervals, harm-specific residuals, and class-aware risk/coverage curves.
- Safer judge-facing terminology that does not imply efficacy or prescribe an action.
- GPT-5.6 Evidence Conflict Auditor through the Responses API and Structured Outputs.
- Deterministic output validator and fallback that prevent the model from changing scientific data.
- Privacy allowlist excluding raw FASTA, filename, checksum, free-form user text, secrets, and personal data from OpenAI requests.
- Adversarial tests for mutation, hallucinated identifiers, injection, timeout, invalid output, and missing credentials.
- One-click, clearly labeled precomputed verified judge example with frozen-test provenance.
- 90-second Judge Mode with four guided proof points: verified case, Firewall Replay, constrained GPT audit, and Evidence Passport.
- Firewall Replay separating the statistical layer, known biological evidence, safety triggers, and immutable final assessment.
- Human-review worklist that prioritizes no-calls and laboratory handoff without ranking or recommending antibiotics.
- Executable 12-case adversarial guardrail suite exposed through the API and interface; this evaluates deterministic model-output controls, not biological performance.
- Evidence Passport with sample digest, annotation runtime, policy digest, model coverage, OpenAI privacy boundary, and frozen-split provenance.
- Downloadable JSON separating scientific report from optional language-model audit.
- Single-service Google Cloud Run deployment with Secret Manager and bounded scaling.
- Transactional Firestore enforcement for a USD 5 OpenAI audit budget, a
  three-audits-per-browser daily limit, payload bounds, and machine-readable
  fail-closed reasons.
- Apache-2.0 project license and third-party notices.

## Human and tool roles

Abel Mancilla is the sole project owner and team member. He selected the problem, data policy, scientific boundaries, model strategy, evaluation interpretation, product design, and submission claims. Codex was used as a software-development tool for repository inspection, implementation assistance, tests, documentation, and review. It is not listed as an author, team member, or coauthor.

## Required final evidence

- Permanent Cloud Run URL and health/readiness smoke checks.
- Public GitHub repository with license and green CI.
- Video no longer than 2:50 showing the running product rather than slides.
- Devpost prior-work/new-work disclosure consistent with this document.
- Feedback/session identifier required by the event form.
- Explicit research-only and independent-external-validation limitations.
