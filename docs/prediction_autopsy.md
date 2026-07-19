# ResistSense Prediction Autopsy

Status date: 2026-07-19.

This artifact exposes genuine errors from the frozen grouped test set. It is a
research audit, not clinical validation, and does not support treatment
recommendations. Standard laboratory testing remains required.

## What the firewall changed

Across 2,185 genome/antibiotic test rows, the selected base classifiers made 68
errors. The firewall converted 55 of them (80.9%) into `no_call`; 13 incorrect results
were still emitted. Both outcomes remain visible.

| Antibiotic | Base errors | Prevented | Residual emitted errors | Prevention fraction |
|---|---:|---:|---:|---:|
| Ampicillin | 20 | 16 | 4 | 80.0% |
| Cefotaxime | 8 | 7 | 1 | 87.5% |
| Ciprofloxacin | 5 | 4 | 1 | 80.0% |
| Gentamicin | 14 | 14 | 0 | 100.0% |
| Trimethoprim/sulfamethoxazole | 21 | 14 | 7 | 66.7% |

## Reproducible case selection

For each antibiotic, the autopsy selects the highest-confidence base-model
error blocked by the firewall and, when one exists, the highest-confidence
incorrect result that escaped the firewall. This deterministic policy yields
nine cases:

| Sample | Antibiotic | Category | Laboratory | Model | Confidence | Final output / barrier |
|---|---|---|---|---|---:|---|
| 562.99241 | Ampicillin | Prevented | Susceptible | Resistant | 100.0% | `no_call`: OOD |
| 562.100287 | Ampicillin | Residual | Susceptible | Resistant | 99.9% | `probable_failure` |
| 562.100547 | Cefotaxime | Prevented | Resistant | Susceptible | 100.0% | `no_call`: OOD |
| 562.100775 | Cefotaxime | Residual | Resistant | Susceptible | 99.1% | `probable_efficacy` |
| 562.100786 | Ciprofloxacin | Prevented | Resistant | Susceptible | 99.7% | `no_call`: OOD |
| 562.100856 | Ciprofloxacin | Residual | Resistant | Susceptible | 99.8% | `probable_efficacy` |
| 562.16325 | Gentamicin | Prevented | Resistant | Susceptible | 100.0% | `no_call`: OOD |
| 562.11347 | Trimethoprim/sulfamethoxazole | Prevented | Resistant | Susceptible | 99.6% | `no_call`: OOD |
| 562.98504 | Trimethoprim/sulfamethoxazole | Residual | Resistant | Susceptible | 95.9% | `probable_efficacy` |

The cases deliberately include residual errors. High confidence is not proof
of correctness, and marker evidence is presented as evidence rather than a
causal claim.

## Reproduction and presentation

```powershell
python scripts\build_prediction_autopsy.py
```

The command writes `artifacts/evaluation/prediction_autopsy.json`. The FastAPI
endpoint `/api/v1/prediction-autopsy` exposes only the selected audit fields;
it does not expose FASTA sequences. The React client renders the aggregate
error counts and all nine cases under **Prediction Autopsy**.
