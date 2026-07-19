# ResistSense frozen-test validation

Status date: 2026-07-19.

ResistSense is a research prototype. These results do not establish clinical
validity and do not support treatment recommendations. Standard laboratory
testing remains required for every result.

## Evaluation contract

- Cohort: 2,909 *Escherichia coli* genomes with laboratory-only BV-BRC labels.
- Frozen grouped test set: 437 genomes from 198 cgMLST HC50 groups. It has
  already been inspected during development and is not external validation.
- Endpoints: five antibiotics, yielding 2,185 test genome/antibiotic rows.
- Baseline features: 206 AMRFinderPlus gene/mutation indicators. The selected
  ciprofloxacin ensemble additionally uses 512 hashed k-mers and three
  assembly-QC variables.
- Dataset SHA-256:
  `5f404ca451c12b51943484a4549d9d8dc5643015ae33d699673f2586e7472d09`.
- Probability calibration, conformal calibration/OOD, and test use disjoint
  genetic groups. No group crosses a partition.
- Confidence intervals use 1,000 genetic-group bootstrap replicates.
- Independent target alignment completed for all 437 test genomes.

## Selected model results

The recommended AMRFinder logistic baseline is used unless five-fold grouped
cross-validation on training groups shows a mean balanced-accuracy gain of at
least 0.01 and the full ensemble ties or improves in at least four folds. This
predeclared rule selects the full ensemble only for ciprofloxacin. Every model
uses a separate Platt calibration split and uniform conformal alpha of 0.05.

| Antibiotic | Strategy | Balanced accuracy (95% group-bootstrap CI) | AUROC | ECE | Conformal coverage | Firewall coverage | Selective accuracy |
|---|---|---:|---:|---:|---:|---:|---:|
| Ampicillin | AMRFinder logistic | 0.951 (0.919-0.970) | 0.944 | 0.028 | 0.954 | 0.240 | 0.962 |
| Cefotaxime | AMRFinder logistic | 0.875 (0.796-0.944) | 0.932 | 0.021 | 0.991 | 0.696 | 0.997 |
| Ciprofloxacin | Full ensemble | 0.963 (0.874-0.993) | 0.969 | 0.017 | 0.991 | 0.712 | 0.997 |
| Gentamicin | AMRFinder logistic | 0.741 (0.621-0.917) | 0.813 | 0.027 | 0.954 | 0.792 | 1.000 |
| Trimethoprim/sulfamethoxazole | AMRFinder logistic | 0.932 (0.898-0.961) | 0.956 | 0.045 | 0.941 | 0.673 | 0.976 |

Firewall coverage is the fraction receiving `probable_failure` or
`probable_efficacy`; the remainder receive a machine-readable `no_call`.
Selective accuracy is calculated only on emitted results.

## Training-only branch selection

The selection audit uses only frozen training groups. The delta is full
ensemble minus the challenge-recommended AMRFinder logistic baseline.

| Antibiotic | Mean five-fold delta | Non-negative folds | Selected strategy |
|---|---:|---:|---|
| Ampicillin | -0.033 | 0/5 | AMRFinder logistic |
| Cefotaxime | -0.052 | 0/5 | AMRFinder logistic |
| Ciprofloxacin | +0.017 | 4/5 | Full ensemble |
| Gentamicin | -0.033 | 1/5 | AMRFinder logistic |
| Trimethoprim/sulfamethoxazole | -0.007 | 1/5 | AMRFinder logistic |

The release trainer refuses to run when the configured strategy differs from
`artifacts/evaluation/model_selection.json`.

## Safety findings and limitations

- Cefotaxime now filters AMRFinderPlus evidence by the `CEPHALOSPORIN`
  subclass. Intrinsic broad `blaEC` is no longer treated as cefotaxime-specific
  conflict evidence. Firewall coverage is 69.6%, but resistant recall is 0.750
  and still requires external review.
- Gentamicin has few resistant test cases. The selected baseline resistant
  recall is 0.481 and its confidence interval is wide, so perfect selective
  accuracy must not be overinterpreted.
- All empirical conformal coverages exceed 94% under the uniform 95% target.
- OOD abstention remains class- and endpoint-sensitive and is reported rather
  than interpreted as biological novelty.
- This is an internal grouped test of a self-curated BV-BRC cohort. Independent
  external validation remains outstanding.

## Reproduction

```powershell
python scripts\select_model_strategy.py
python scripts\train_baselines.py `
  --features data\processed\features\resistsense_features.csv
python scripts\export_test_predictions.py --target-workers 16
python scripts\evaluate_predictions.py `
  --predictions artifacts\evaluation\predictions.csv `
  --bootstrap-replicates 1000
python scripts\evaluate_feature_ablation.py --bootstrap-replicates 1000
python scripts\build_prediction_autopsy.py
python scripts\validate_release.py
```

Machine-readable evidence is stored in `artifacts/evaluation/predictions.csv`,
`artifacts/evaluation/evaluation.json`, and
`artifacts/evaluation/model_selection.json`. The release decision is stored in
`artifacts/evaluation/release_gate.json`. Genuine frozen-test error cases are
documented in `docs/prediction_autopsy.md` and
`artifacts/evaluation/prediction_autopsy.json`.
