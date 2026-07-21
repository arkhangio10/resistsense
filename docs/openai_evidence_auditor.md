# GPT-5.6 Evidence Conflict Auditor

The OpenAI layer is intentionally downstream of the deterministic ResistSense scientific pipeline. It audits whether the already-computed report communicates evidence, contradictions, and uncertainty consistently. It cannot select antibiotics, modify an outcome, change a probability, add a marker, suppress a `no-call`, or make a clinical claim.

## API contract

- Endpoint: `POST /api/v1/evidence-audit`
- OpenAI API: Responses API with Structured Outputs
- Model: `gpt-5.6-sol`
- Reasoning effort: `low`
- Prompt version: `evidence-conflict-auditor-v1`
- Runtime configuration: `configs/resistsense.yaml`
- Secret: server-side `OPENAI_API_KEY`

The backend first validates the scientific report with the deterministic communication policy. It then creates a strict allowlisted payload containing:

- genome-quality counts and machine-readable reason codes;
- annotation availability and pinned tool versions;
- the existing antibiotic status and calibrated probability;
- known biological evidence, separately labeled from statistical associations;
- target, conformal, OOD, model-agreement, and `no-call` fields;
- backend-generated evidence identifiers.

The following are never included in the OpenAI request:

- raw FASTA or any sequence fragment;
- original upload filename;
- genome checksum;
- free-form user text;
- secrets or personal data.

## Output validation

The OpenAI response must conform to the Pydantic schema in `src/resistsense/evidence_auditor.py`. A second deterministic validator rejects the response if it:

1. changes an antibiotic set, status, or calibrated probability;
2. cites an unknown evidence identifier;
3. changes the exact result/no-call/marker counts;
4. changes the prompt version;
5. removes the laboratory-confirmation requirement;
6. hides a `review_required` finding behind a `consistent` status;
7. emits clinical, diagnostic, dosing, prescribing, or treatment language.

Any timeout, SDK error, malformed structured output, safety rejection, or missing API key produces a deterministic fallback. The scientific report remains unchanged and available.

For a successful OpenAI call, the API response exposes only operational telemetry: the OpenAI request/response identifiers and aggregate input, output, and total token counts. It does not log or return the OpenAI payload, raw sequence, filename, checksum, or secret. The deterministic fallback leaves these telemetry fields empty.

## Verification

```powershell
python -m pytest tests\test_evidence_auditor.py tests\test_api.py
```

The adversarial suite covers prompt injection in identifiers, original filename/checksum exclusion, status and probability mutation, unknown evidence, hallucinated antibiotic fields, changed counts, removed laboratory confirmation, hidden review findings, timeout, invalid output, missing credentials, and validator rejection.

## Interpretation boundary

The model is a communication and consistency auditor, not the AMR predictor. ResistSense remains useful without OpenAI: all FASTA analysis, evidence extraction, calibrated prediction, safety barriers, abstention, class-aware evaluation, and downloadable scientific output are deterministic backend functions.
