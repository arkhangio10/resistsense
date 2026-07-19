# ResistSense repository guidance

## Product boundary

ResistSense is a defensive research prototype for antimicrobial-resistance
decision support. It must never design, modify, strengthen, or recommend
changes to an organism. Every antibiotic result is provisional and must say
that standard laboratory testing is required.

## Safety invariants

- Never turn missing resistance markers into proof of susceptibility.
- Missing models, annotations, targets, calibration, or genome quality produce
  `no-call`.
- Never report a treatment recommendation.
- Keep known biological evidence separate from statistical associations.
- Do not split near-identical or genetically related genomes across train and
  test sets.

## Project commands

- Install backend: `python -m pip install -e .[dev]`
- Run tests: `python -m pytest`
- Run API: `python -m uvicorn resistsense.api:app --reload --port 8000`
- Run frontend: `cd frontend && npm run dev`
- Build frontend: `cd frontend && npm run build`

## Change discipline

- `configs/resistsense.yaml` is the source of truth for runtime policy.
- Generated data and models do not belong in Git.
- Add tests for every change to decision or abstention logic.
- Preserve a machine-readable reason for every `no-call`.
