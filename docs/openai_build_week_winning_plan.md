# ResistSense — OpenAI Build Week Winning Plan

**Status:** core implementation and credentialed GPT verification complete; permanent Cloud Run deployment, video, and final submission remain external execution tasks
**Prepared:** 2026-07-20
**Submission deadline:** 2026-07-21 17:00 PDT / 19:00 America/Lima
**Track:** Work & Productivity
**Owner:** Abel Mancilla, solo participant

## 1. Objective

Turn the existing ResistSense research prototype into a reliable, judge-ready
OpenAI Build Week submission with a credible chance of placing in the top two
of the Work & Productivity track.

The submission must demonstrate a meaningful extension completed during the
Build Week submission period. The extension will center on a safety-first AMR
workflow, a GPT-5.6 evidence-conflict auditor, class-aware validation, a
complete product experience, and a permanent public deployment.

Winning thesis:

> Most AMR predictors force a binary answer. ResistSense challenges every
> prediction through independent safety barriers, abstains when the evidence
> is unsafe, and uses GPT-5.6 to audit and communicate the evidence without
> prescribing or overriding the scientific model.

## 2. Non-negotiable product and safety boundaries

1. ResistSense is a defensive research prototype, not a diagnostic device.
2. It never recommends, ranks, doses, or selects treatment.
3. Absence of a resistance marker is never proof of susceptibility.
4. Missing models, annotations, calibration, targets, species identity, or
   adequate genome quality produce `no-call`.
5. Known biological mechanisms remain separate from statistical associations.
6. Every emitted result requires standard laboratory confirmation.
7. GPT-5.6 cannot change a status, probability, marker, or safety decision.
8. Raw FASTA, DNA sequence, original filename, and secrets are never sent to
   OpenAI.
9. No AI tool will be listed as a coauthor and commits will not contain an AI
   `Co-authored-by` trailer. Codex will be documented as a development tool, as
   required by the hackathon.
10. All judge-facing product text, README sections, video, testing
    instructions, and submission materials will be in English.

## 3. Current truth that must be presented honestly

The current frozen internal evaluation contains 437 genomes and five
antibiotic endpoints. Overall selective accuracy is high, but class-conditional
coverage is highly asymmetric:

| Antibiotic | Resistant-class coverage | Susceptible-class coverage | Incorrect susceptible calls among emitted resistant cases |
|---|---:|---:|---:|
| Ampicillin | 55.2% | 1.6% | 0/101 |
| Cefotaxime | 12.5% | 74.1% | 1/4 |
| Ciprofloxacin | 1.8% | 81.4% | 1/1 |
| Gentamicin | 0.0% | 84.4% | No resistant cases emitted |
| Trimethoprim/sulfamethoxazole | 32.2% | 80.3% | 2/38 |

Consequences:

- Global selective accuracy cannot be shown without class-specific coverage.
- The existing release gate is a reproducibility/research gate, not evidence
  of clinical performance.
- Ciprofloxacin and gentamicin must not be described as having safe balanced
  output coverage.
- Endpoints without sufficient emitted validation support must be labeled
  `abstain-dominant` or `insufficient class-conditional validation`.
- The frozen test has already been inspected. Runtime thresholds must not be
  retuned against it and then re-reported as an unbiased test.
- External validation remains future work unless an entirely independent,
  overlap-free cohort is frozen before evaluation.

## 4. How the submission will score against the judging criteria

| Criterion | Evidence ResistSense must show |
|---|---|
| Technological Implementation | Real FASTA pipeline, AMRFinderPlus, calibrated grouped models, conformal/OOD firewall, deterministic GPT-5.6 validation, tests, permanent deployment, documented Codex collaboration |
| Design | One-click verified sample, understandable progress, separate scientific and GPT layers, responsive English UI, downloadable traceable report, graceful failures |
| Potential Impact | Concrete workflow for clinical microbiology and genomic-surveillance teams; reduced manual evidence review; explicit limitations; no treatment claims |
| Quality of the Idea | A Genome Firewall that quantifies abstention, exposes prevented and escaped errors, and uses GPT-5.6 as a constrained evidence challenger rather than a predictor |

## 5. Exact implementation scope for the submission

Only the following six product capabilities are in the winning submission
scope:

1. Existing scientific FASTA analysis and safety firewall.
2. Class-aware safety report and honest endpoint limitations.
3. GPT-5.6 Evidence Conflict Auditor.
4. Prediction Autopsy as the central proof of value.
5. One-click verified judge sample and downloadable provenance report.
6. Permanent Google Cloud deployment.

The following are explicitly out of submission scope:

- New species.
- Treatment recommendations or AWaRe-based drug selection.
- Wastewater or metagenomic claims.
- Unitig, GNN, CNN, DNABERT, or HyenaDNA experiments.
- Retraining thresholds against the already-inspected frozen test.
- Claims of FDA, CLSI, clinical, diagnostic, GLASS, or regulatory compliance.
- A rushed external-validation claim based on a small or overlapping cohort.

## 6. Phase A — Establish a safe baseline

**Target duration:** 20 minutes
**Priority:** P0

When implementation begins:

1. Confirm the working tree and current branch.
2. Create branch `codex/build-week-v2`.
3. Record current commit SHA and CI status.
4. Run existing backend and frontend tests in the supported environments.
5. Preserve all current artifacts and hashes.
6. Do not retrain models unless an implementation defect requires it.

Acceptance criteria:

- Baseline test results are recorded.
- Existing frozen artifacts remain unchanged.
- No unrelated user changes are overwritten.

Planned commit:

```text
chore: establish Build Week extension baseline
```

## 7. Phase B — Class-aware safety evaluation

**Target duration:** 90–120 minutes
**Priority:** P0 scientific credibility

### Deliverables

- `scripts/evaluate_selective_safety.py`
- `artifacts/evaluation/selective_safety.json`
- `docs/selective_safety.md`
- Tests for all metric definitions and zero-denominator behavior.
- An extension to the release report that distinguishes research readiness
  from clinical eligibility.

### Required metrics per antibiotic

1. Number of resistant and susceptible test cases.
2. Base-model false-susceptible and false-resistant counts.
3. Overall firewall coverage.
4. Coverage conditioned on the true resistant class.
5. Coverage conditioned on the true susceptible class.
6. Incorrect susceptible calls among emitted resistant cases.
7. Incorrect resistant calls among emitted susceptible cases.
8. The same errors divided by all reference cases, clearly distinguished from
   error conditional on emission.
9. `no-call` count by reason and class.
10. Genetic-group bootstrap confidence intervals.
11. Risk-coverage curve data.
12. Minimum emitted support per class.

### Release semantics

The report must contain two independent statuses:

```text
research_demo_status
clinical_release_status
```

Expected current state:

```text
research_demo_status: pass
clinical_release_status: fail_not_externally_validated
```

No endpoint may claim balanced selective performance when one class has
insufficient emitted support. The UI will show a limitation badge rather than
hiding this fact.

FDA-style VME/ME definitions may be shown only as contextual exploratory
metrics. Essential agreement cannot be claimed because ResistSense does not
predict MIC. No regulatory compliance language is allowed.

Acceptance criteria:

- Metrics reproduce the exact counts in Section 3.
- Zero emitted resistant cases never become a misleading `0% error` result.
- Every rate includes its numerator and denominator.
- The release report cannot pass clinical eligibility.
- Tests cover class imbalance, no-calls, empty classes, and residual errors.

Planned commit:

```text
feat: add class-aware selective safety evaluation
```

## 8. Phase C — Safe terminology and evidence separation

**Target duration:** 45–60 minutes
**Priority:** P0 safety and design

Judge-facing terminology:

| Current | Judge-facing replacement |
|---|---|
| Probable failure | Resistance signal |
| Probable efficacy | Susceptibility-compatible signal |
| No-call | No-call — insufficient or conflicting evidence |

Every result must display:

1. `Known biological evidence`.
2. `Statistical association`.
3. `Safety barriers`.
4. `Validation limitation`.
5. `Laboratory confirmation required`.

Backward-compatible API values may remain temporarily, but the UI and report
must not use treatment-adjacent language. If API enums are migrated, a
versioned compatibility layer and decision-logic tests are required.

Specific limitation badges:

- `Abstain-dominant for resistant validation cases`.
- `Internal grouped validation only`.
- `External validation incomplete`.
- `Research prototype — not a treatment recommendation`.

Acceptance criteria:

- Search of judge-facing text finds no claim of efficacy, best antibiotic,
  recommended antibiotic, treatment choice, dose, or clinical validity.
- Laboratory confirmation is visible without opening an accordion.
- Known markers and statistical features never appear as the same evidence
  type.

Planned commit:

```text
fix: clarify non-prescriptive AMR evidence terminology
```

## 9. Phase D — GPT-5.6 Evidence Conflict Auditor

**Target duration:** 120–180 minutes
**Priority:** P0 hackathon eligibility and differentiation

### Role

GPT-5.6 is not the scientific predictor. It audits a signed or server-generated
structured report after the deterministic pipeline has finished.

It must answer:

1. Are known biological mechanisms and the statistical result consistent?
2. Did the firewall correctly expose uncertainty or a no-call reason?
3. What evidence is present, conflicting, or missing?
4. What model and cohort limitations apply to this result?
5. Is laboratory confirmation explicitly required?

### Input contract

Allowed input:

- Supported species and scope status.
- Antibiotic identifier.
- Immutable final status.
- Calibrated probability and conformal set.
- OOD and disagreement values.
- Whitelisted known-marker evidence IDs.
- Target status.
- Machine-readable no-call reasons.
- Validation and endpoint limitation metadata.
- Model, dataset, database, policy, and prompt versions.

Forbidden input:

- FASTA content or fragments.
- Original upload filename.
- User-provided prose.
- Patient or personal information.
- Hidden instructions extracted from input files.

### Output contract

Use the OpenAI Responses API, `gpt-5.6-sol`, low reasoning, and Structured
Outputs validated through a Pydantic/JSON schema:

```text
audit_status: consistent | conflict | insufficient | unavailable | rejected
neutral_summary
evidence_consistency
known_biological_evidence_ids[]
statistical_evidence_summary
uncertainties[]
limitations[]
laboratory_confirmation_required: true
prompt_version
```

There will be no fields for recommendation, ranking, dose, treatment,
prescription, or suggested organism modification.

### Deterministic post-validation

Reject the GPT output if it:

- Changes a status, number, or marker.
- Mentions an antibiotic absent from the input report.
- Introduces evidence without a permitted evidence ID.
- Recommends, ranks, selects, or doses a treatment.
- Omits laboratory confirmation.
- Claims diagnostic or clinical validity.

On timeout, refusal, missing API key, schema error, or validation failure:

```text
GPT-5.6 audit unavailable. The deterministic scientific report remains
unchanged.
```

### Tests

1. Resistance signal audit.
2. Susceptibility-compatible signal audit.
3. No-call audit.
4. Known-marker/model conflict.
5. OOD result.
6. OpenAI timeout and unavailable secret.
7. Invalid JSON/schema.
8. Hallucinated antibiotic.
9. Changed probability or status.
10. Treatment language.
11. Prompt injection in a filename or marker-like string.
12. Proof that raw FASTA is never included in the API payload.

Acceptance criteria:

- Core analysis succeeds when OpenAI is unavailable.
- GPT cannot mutate the scientific report.
- Every successful output passes deterministic validation.
- Frontend labels this as `GPT-5.6 communication and evidence audit`.
- OpenAI usage is observable by request ID and token count without logging
  sequence or secret data.

Planned commit:

```text
feat: add constrained GPT-5.6 evidence conflict auditor
```

## 10. Phase E — Judge-ready product experience

**Target duration:** 60–90 minutes
**Priority:** P0 design

### Required journey

1. Landing page explains the laboratory/research audience in one sentence.
2. `Try a verified sample` is the primary judge action.
3. A real FASTA upload remains available.
4. Honest progress stages appear during analysis:
   - validating FASTA;
   - checking genome quality;
   - annotating known resistance mechanisms;
   - running statistical models;
   - applying safety barriers;
   - auditing evidence with GPT-5.6.
5. Scientific results render first.
6. GPT audit renders separately and cannot block the scientific result.
7. Prediction Autopsy shows:
   - 68 base errors;
   - 55 blocked as no-call;
   - 13 residual emitted errors;
   - both prevented and escaped examples.
8. A downloadable JSON report includes provenance and limitations.

### Verified sample strategy

The one-click path must be reliable and clearly labeled:

- Use a repository-authorized sample with no patient information.
- The full pipeline remains reproducible.
- A versioned precomputed demonstration report may be used for instant judge
  playback only if the UI explicitly labels it `verified demo report` and
  provides a separate `run full analysis` action.
- Never imply a precomputed result was generated live.

### Frontend performance

- Dynamically load the Three.js visualization.
- Respect reduced-motion preferences.
- Provide a static fallback.
- Keep the scientific result readable if WebGL fails.
- Do not spend submission-critical time redesigning decorative animation.

Acceptance criteria:

- A first-time judge reaches a meaningful result in under 90 seconds using the
  verified demo path.
- All content is readable at 1366×768 and on a mobile-width viewport.
- Keyboard navigation and visible focus work.
- GPT failure produces a calm, non-blocking state.
- The app clearly states what it cannot determine.

Planned commit:

```text
feat: add judge-ready evidence audit experience
```

## 11. Phase F — Documentation, license, and Build Week evidence

**Target duration:** 60 minutes
**Priority:** P0 eligibility

### Repository changes

1. Add an appropriate project license, expected choice Apache-2.0 after
   confirming compatibility with bundled dependencies and data artifacts.
2. Add third-party notices and data/tool provenance.
3. Correct the README live-demo section and remove any implication that the
   failed Hugging Face Space is already permanent.
4. Add a `Build Week Extension` section that distinguishes prior work from new
   work.
5. Describe Codex collaboration and human decisions.
6. Describe GPT-5.6's constrained product role.
7. Include setup instructions, verified sample instructions, limitations, and
   testing steps.
8. Link the permanent Google Cloud URL after deployment.

### Required prior/new-work table

| Prior project work | Build Week extension |
|---|---|
| BV-BRC curation and grouped split | Class-aware selective-safety evaluation |
| AMRFinderPlus and calibrated baseline models | GPT-5.6 Evidence Conflict Auditor |
| Conformal/OOD firewall | Deterministic LLM output validation and adversarial tests |
| React visualization | Judge-ready evidence audit flow and verified sample |
| Temporary/local deployment | Permanent Google Cloud deployment |

### Codex documentation

Document that Codex helped:

- Audit the existing architecture and evaluation.
- Discover the class-conditional coverage limitation.
- Plan and implement tests and constrained GPT integration.
- Improve deployment and reproducibility.
- Prepare the submission and documentation.

Document the owner's decisions:

- Keep the product non-prescriptive.
- Preserve simple models where grouped validation favored them.
- Reject an unjustified deep-learning pivot.
- Separate biological and statistical evidence.
- Expose residual errors rather than hide them.

Acceptance criteria:

- Public repository has relevant licensing.
- README explicitly includes Codex and GPT-5.6.
- Prior and new work are distinguishable by dated commits.
- No false permanent-deployment statement remains.
- All testing instructions work from a clean environment.

Planned commit:

```text
docs: document Build Week extension and project licensing
```

## 12. Phase G — Permanent Google Cloud deployment

**Target duration:** 90–150 minutes
**Priority:** P0 functionality

### Required user decision at the start

Create or select a dedicated Google Cloud project such as
`resistsense-build-week` and enable billing. The currently selected
`agente-pm-hackathon` project has billing disabled. No other billed project may
be reused without the owner's explicit choice.

### Initial architecture

Use one public Cloud Run service containing:

- React/vinext frontend.
- FastAPI backend.
- Nginx or equivalent same-origin routing.
- Frozen model artifacts.
- AMRFinderPlus runtime and pinned database.

Configuration target:

```text
region: us-central1
cpu: 2
memory: 2 GiB initially, raise only after measured failure
concurrency: 1
min instances: 0
max instances: 1
timeout: 600–900 seconds
port: 0.0.0.0:$PORT
request-based billing: enabled
startup CPU boost: enabled
```

Use:

- Artifact Registry for the container.
- Secret Manager for `OPENAI_API_KEY`.
- A restricted production origin or same-origin routing.
- Structured request IDs and logs that exclude filename and sequence.
- Startup/readiness probes that verify models and required tools.
- Ephemeral temporary storage only; delete the FASTA after analysis.
- A Google Cloud budget alert and OpenAI usage limit.

### Deployment tests

1. Open the URL in an incognito session.
2. `/health` succeeds.
3. Readiness verifies models and AMRFinderPlus.
4. Verified demo path succeeds.
5. One real FASTA succeeds.
6. Invalid FASTA produces safe `no-call`/validation output.
7. Missing OpenAI secret leaves core analysis available.
8. Two simultaneous requests do not overload the container.
9. Restart the service and repeat the smoke test.
10. Confirm the URL survives after the development laptop is turned off.

Acceptance criteria:

- Stable HTTPS URL.
- No dependency on Cloudflare Quick Tunnel or the owner's laptop.
- Core and GPT results function as documented.
- Maximum instance count prevents uncontrolled cost.
- Secrets do not appear in the image, repository, browser, or logs.

Planned commit:

```text
deploy: add production Google Cloud Run service
```

## 13. Phase H — Final verification

**Target duration:** 45 minutes
**Priority:** P0

Required checks:

- Backend unit and integration tests pass.
- Frontend lint, tests, and production build pass.
- Class-aware safety evaluation reproduces frozen counts.
- GPT adversarial tests pass.
- Container builds from a clean checkout.
- Cloud Run smoke test passes.
- Verified sample and real upload are both tested.
- README URLs are correct.
- No generated training data, FASTA, secrets, or API keys are staged.
- Git working tree contains only intended changes.
- GitHub Actions is green on the final commit.

Do not submit while CI is pending or failing unless the failure is proven to be
an unrelated external outage and is clearly documented.

## 14. Three-minute video plan

**Maximum:** 2 minutes 50 seconds to preserve margin.
**Language:** English, with clear audio.
**Hosting:** Public YouTube link.

| Time | Content |
|---|---|
| 0:00–0:15 | Problem: conventional AMR predictors can be confidently wrong |
| 0:15–0:30 | Product: ResistSense predicts, challenges, and abstains |
| 0:30–1:10 | One-click verified sample and Genome Firewall stages |
| 1:10–1:35 | Separate biological evidence, statistical association, and no-call barriers |
| 1:35–1:55 | Prediction Autopsy: 55 of 68 base errors blocked, 13 residual errors exposed |
| 1:55–2:20 | GPT-5.6 auditor finds/communicates evidence conflict and cannot alter the result |
| 2:20–2:35 | Dataset, grouped split, class-aware limitations, laboratory confirmation |
| 2:35–2:45 | How Codex accelerated the work and where the owner made key decisions |
| 2:45–2:50 | Closing: `Predict. Challenge. Abstain.` and permanent demo URL |

The video must show a functioning product, not slides alone. Do not use
copyrighted music, third-party marks without permission, or unverified medical
claims.

## 15. Devpost submission checklist

- [ ] Correct event and Work & Productivity category.
- [ ] Project title: `ResistSense — A Genome Firewall for AMR Evidence`.
- [ ] English short description.
- [ ] English structured description.
- [ ] Public permanent Cloud Run URL.
- [ ] Public GitHub repository URL.
- [ ] Relevant repository license.
- [ ] Public YouTube video under three minutes with audio.
- [ ] Technologies: React, TypeScript, Python, FastAPI, scikit-learn,
      AMRFinderPlus, BV-BRC, OpenAI GPT-5.6, Codex, Docker, Google Cloud Run.
- [ ] `/feedback` Codex Session ID for the thread containing the majority of
      the Build Week core extension work.
- [ ] Testing instructions and verified sample.
- [ ] Prior work versus Build Week work documented.
- [ ] Submission remains available free of charge through the judging period.
- [ ] Final submission completed before 19:00 America/Lima.

## 16. Tomorrow's timeboxed execution schedule

Suggested schedule if work begins at 08:00 America/Lima:

| Time | Work | Exit condition |
|---|---|---|
| 08:00–08:20 | Phase A baseline | Tests/status recorded, branch ready |
| 08:20–09:50 | Phase B class-aware evaluation | Correct metrics, tests, research/clinical status split |
| 09:50–10:35 | Phase C terminology | Non-prescriptive UI/report language |
| 10:35–13:05 | Phase D GPT-5.6 auditor | Structured audit, deterministic validator, failure fallback, tests |
| 13:05–14:05 | Phase E judge experience | Verified sample, audit card, Autopsy story |
| 14:05–15:00 | Phase F README/license | Eligibility documentation complete |
| 15:00–16:30 | Phase G Cloud Run | Permanent URL and smoke test |
| 16:30–17:10 | Phase H final verification | CI/build/smoke green |
| 17:10–18:00 | Record and upload video | Public YouTube URL verified |
| 18:00–18:35 | Complete Devpost | Every required field and Session ID present |
| 18:35–19:00 | Final buffer | Submit and verify confirmation |

If starting later, preserve the final 110 minutes for the video, Devpost, and
submission. Cut decorative animation and publication-only work first. Never
cut GPT-5.6 integration, permanent demo, licensing, `/feedback`, or required
submission materials.

## 17. Stop/go rules

1. **No GPT integration by 13:05:** stop UI polish and finish the constrained
   integration; it is a baseline hackathon requirement.
2. **No permanent URL by 16:00:** stop all scientific stretch work and resolve
   deployment.
3. **Cloud billing cannot be enabled:** immediately choose an authorized
   permanent fallback; do not depend on a laptop-hosted tunnel.
4. **A core safety test fails:** do not hide it and do not record the final
   video until fixed or the affected feature is disabled honestly.
5. **Class-aware report exposes insufficient support:** label the endpoint
   accordingly; do not tune on the frozen test to improve the headline.
6. **External validation is not complete by the submission freeze:** state it
   as future work; never relabel an internal split as external.
7. **Time remaining is under two hours:** freeze code, run final smoke tests,
   record the video, obtain `/feedback`, and submit.

## 18. Post-submission scientific roadmap

These tasks improve publishability but must not endanger the submission:

1. Drug-specific determinant mapping, including intrinsic-marker exclusions.
2. Label-conditional/Mondrian conformal evaluation.
3. OOD evaluation by class, genetic group, geography, and time.
4. Species/contamination gate with explicit *E. coli*–*Shigella* ambiguity.
5. ResFinder rule-only benchmark.
6. Independently frozen Liverpool or NCBI Pathogen Detection validation
   cohort with accession and near-duplicate exclusion.
7. Risk-coverage confidence intervals under external distribution shift.
8. TRIPOD+AI report and PROBAST+AI self-assessment.
9. Preregistered model-comparison protocol.
10. Only then consider unitigs, multi-task learning, or another species.

Potential external cohort sources:

- University of Liverpool 762-isolate clinical *E. coli* WGS+AST dataset.
- NCBI Pathogen Detection AST Browser, after strict curation and overlap
  removal.

## 19. Final definition of done

ResistSense is ready to submit only when all statements below are true:

- The public demo works after the laptop is off.
- The scientific core works without OpenAI.
- GPT-5.6 performs a meaningful constrained audit and cannot alter results.
- Raw sequence never leaves the scientific backend.
- Results are non-prescriptive and require laboratory confirmation.
- Class-specific coverage and residual errors are visible.
- Prediction Autopsy exposes both prevented and escaped errors.
- Prior work and Build Week additions are clearly separated.
- Repository licensing, README, sample, tests, deployment, video, and
  `/feedback` Session ID satisfy the official submission requirements.
- CI and public smoke tests are green.
- The submission is completed before the deadline with at least 20 minutes of
  buffer.

## 20. Expected competitive outcome

This plan cannot guarantee a prize. It is designed to maximize all four equally
weighted judging criteria while preventing scientific overclaiming.

Estimated outcome if executed completely and presented well:

- Pass eligibility/viability: 95%+.
- Reach a genuinely competitive group: 20–35%.
- Potential shortlist: 15–30%.
- Top-two prize in Work & Productivity: approximately 6–10%.
- First place: approximately 3–5%.

The largest differentiator is not raw model accuracy. It is demonstrable,
quantified, and honestly communicated safety under uncertainty.

## 21. Reference anchors

- OpenAI Build Week rules and judging criteria:
  https://openai.devpost.com/rules
- Hu et al. AMR prediction benchmarking:
  https://academic.oup.com/bib/article/25/3/bbae206/7665136
- NCBI Pathogen Detection AST documentation:
  https://www.ncbi.nlm.nih.gov/pathogens/docs/ast/
- University of Liverpool external dataset candidate:
  https://datacat.liverpool.ac.uk/3008/
- TRIPOD+AI:
  https://www.tripod-statement.org/scope/
- PROBAST+AI:
  https://www.bmj.com/content/388/bmj-2024-082505
- FDA AST system guidance, used only as contextual metric guidance:
  https://www.fda.gov/medical-devices/guidance-documents-medical-devices-and-radiation-emitting-products/antimicrobial-susceptibility-test-ast-systems-class-ii-special-controls-guidance-industry-and-fda
- WHO GLASS WGS guidance, future surveillance direction only:
  https://www.who.int/publications/i/item/9789240011007
