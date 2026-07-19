from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.preprocessing import StandardScaler

from resistsense.evaluation import grouped_bootstrap_intervals, standard_metrics


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped))


def _paired_group_delta(
    labels: np.ndarray,
    baseline: np.ndarray,
    candidate: np.ndarray,
    groups: np.ndarray,
    *,
    replicates: int,
    random_state: int,
) -> dict[str, float | int]:
    unique_groups = np.unique(groups)
    indices_by_group = {
        group: np.flatnonzero(groups == group) for group in unique_groups
    }
    rng = np.random.default_rng(random_state)
    deltas = []
    for _ in range(replicates):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        selected = np.concatenate([indices_by_group[group] for group in sampled_groups])
        if len(np.unique(labels[selected])) < 2:
            continue
        baseline_score = balanced_accuracy_score(
            labels[selected], (baseline[selected] >= 0.5).astype(int)
        )
        candidate_score = balanced_accuracy_score(
            labels[selected], (candidate[selected] >= 0.5).astype(int)
        )
        deltas.append(float(candidate_score - baseline_score))
    estimate = balanced_accuracy_score(
        labels, (candidate >= 0.5).astype(int)
    ) - balanced_accuracy_score(labels, (baseline >= 0.5).astype(int))
    return {
        "estimate": float(estimate),
        "lower": float(np.quantile(deltas, 0.025)),
        "upper": float(np.quantile(deltas, 0.975)),
        "probability_candidate_better": float(np.mean(np.asarray(deltas) > 0)),
        "valid_replicates": len(deltas),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the AMRFinder-only logistic baseline with full features"
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/features/resistsense_features.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/feature_ablation.json"),
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    frame = pd.read_csv(
        args.features, dtype={"sample_id": str, "genetic_group": str}
    )
    marker_columns = sorted(
        column for column in frame.columns if column.startswith("feature__marker__")
    )
    if not marker_columns:
        raise ValueError("No AMRFinder marker features found")

    report = {}
    for antibiotic, subset in frame.groupby("antibiotic", sort=True):
        subset = subset.copy()
        labels = subset["label"].astype(str).str.lower().map(
            {"susceptible": 0, "resistant": 1}
        )
        if labels.isna().any():
            raise ValueError(f"Unknown labels for {antibiotic}")
        labels_array = labels.to_numpy(dtype=int)
        partitions = subset["split"].astype(str).str.lower().to_numpy()
        train_idx = np.flatnonzero(partitions == "train")
        probability_idx = np.flatnonzero(partitions == "probability_calibration")
        test_idx = np.flatnonzero(partitions == "test")
        if not len(train_idx) or not len(probability_idx) or not len(test_idx):
            raise ValueError(f"Incomplete frozen split for {antibiotic}")

        marker_features = subset[marker_columns].to_numpy(dtype=float)
        scaler = StandardScaler().fit(marker_features[train_idx])
        estimator = LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=args.random_state,
        ).fit(scaler.transform(marker_features[train_idx]), labels_array[train_idx])
        probability_raw = estimator.predict_proba(
            scaler.transform(marker_features[probability_idx])
        )[:, 1]
        calibrator = LogisticRegression(random_state=args.random_state).fit(
            _logit(probability_raw).reshape(-1, 1), labels_array[probability_idx]
        )
        marker_test_raw = estimator.predict_proba(
            scaler.transform(marker_features[test_idx])
        )[:, 1]
        marker_test_calibrated = calibrator.predict_proba(
            _logit(marker_test_raw).reshape(-1, 1)
        )[:, 1]

        full_columns = sorted(
            column for column in frame.columns if column.startswith("feature__")
        )
        full_features = subset[full_columns].to_numpy(dtype=float)
        full_scaler = StandardScaler().fit(full_features[train_idx])
        full_train = full_scaler.transform(full_features[train_idx])
        full_probability = full_scaler.transform(full_features[probability_idx])
        full_test = full_scaler.transform(full_features[test_idx])
        full_estimators = (
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=args.random_state,
            ),
            HistGradientBoostingClassifier(
                max_iter=150,
                learning_rate=0.06,
                l2_regularization=1.0,
                class_weight="balanced",
                random_state=args.random_state,
            ),
        )
        for estimator in full_estimators:
            estimator.fit(full_train, labels_array[train_idx])
        full_probability_raw = np.column_stack(
            [
                estimator.predict_proba(full_probability)[:, 1]
                for estimator in full_estimators
            ]
        ).mean(axis=1)
        full_calibrator = LogisticRegression(
            random_state=args.random_state
        ).fit(
            _logit(full_probability_raw).reshape(-1, 1),
            labels_array[probability_idx],
        )
        full_test_experts = [
            estimator.predict_proba(full_test)[:, 1]
            for estimator in full_estimators
        ]
        full_logistic = full_test_experts[0]
        full_test_raw = np.column_stack(full_test_experts).mean(axis=1)
        full_ensemble = full_calibrator.predict_proba(
            _logit(full_test_raw).reshape(-1, 1)
        )[:, 1]
        test_labels = labels_array[test_idx]
        test_groups = subset.iloc[test_idx]["genetic_group"].astype(str).to_numpy()

        report[str(antibiotic)] = {
            "feature_counts": {
                "amrfinder_markers": len(marker_columns),
                "full": sum(
                    column.startswith("feature__") for column in frame.columns
                ),
            },
            "amrfinder_logistic_raw": standard_metrics(
                test_labels, marker_test_raw
            ),
            "amrfinder_logistic_calibrated": standard_metrics(
                test_labels, marker_test_calibrated
            ),
            "full_feature_logistic_raw": standard_metrics(
                test_labels, full_logistic
            ),
            "full_ensemble_calibrated": standard_metrics(
                test_labels, full_ensemble
            ),
            "amrfinder_logistic_calibrated_bootstrap_95pct": (
                grouped_bootstrap_intervals(
                    test_labels,
                    marker_test_calibrated,
                    test_groups,
                    replicates=args.bootstrap_replicates,
                    random_state=args.random_state,
                )
            ),
            "full_ensemble_bootstrap_95pct": grouped_bootstrap_intervals(
                test_labels,
                full_ensemble,
                test_groups,
                replicates=args.bootstrap_replicates,
                random_state=args.random_state,
            ),
            "full_minus_amrfinder_logistic_balanced_accuracy": _paired_group_delta(
                test_labels,
                marker_test_calibrated,
                full_ensemble,
                test_groups,
                replicates=args.bootstrap_replicates,
                random_state=args.random_state,
            ),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "antibiotics": len(report),
                "marker_features": len(marker_columns),
                "bootstrap_replicates": args.bootstrap_replicates,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
