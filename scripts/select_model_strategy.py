"""Select the per-antibiotic model branch without consulting frozen-test labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler


def _fit_marker_baseline(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    labels_train: np.ndarray,
    marker_columns: list[str],
    random_state: int,
) -> np.ndarray:
    scaler = StandardScaler().fit(train[marker_columns])
    estimator = LogisticRegression(
        max_iter=3000,
        class_weight="balanced",
        random_state=random_state,
    ).fit(scaler.transform(train[marker_columns]), labels_train)
    return estimator.predict_proba(scaler.transform(validation[marker_columns]))[:, 1]


def _fit_full_ensemble(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    labels_train: np.ndarray,
    feature_columns: list[str],
    random_state: int,
) -> np.ndarray:
    scaler = StandardScaler().fit(train[feature_columns])
    train_features = scaler.transform(train[feature_columns])
    validation_features = scaler.transform(validation[feature_columns])
    estimators = (
        LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=random_state,
        ),
        HistGradientBoostingClassifier(
            max_iter=150,
            learning_rate=0.06,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=random_state,
        ),
    )
    probabilities = []
    for estimator in estimators:
        estimator.fit(train_features, labels_train)
        probabilities.append(estimator.predict_proba(validation_features)[:, 1])
    return np.column_stack(probabilities).mean(axis=1)


def _strategy(deltas: list[float], minimum_mean_gain: float) -> str:
    positive_folds = sum(delta >= 0 for delta in deltas)
    if np.mean(deltas) >= minimum_mean_gain and positive_folds >= len(deltas) - 1:
        return "full_ensemble"
    return "amrfinder_logistic"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the recommended AMRFinder logistic baseline with the full "
            "ensemble using grouped cross-validation on training groups only"
        )
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/features/resistsense_features.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/model_selection.json"),
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--minimum-mean-gain", type=float, default=0.01)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    if args.folds < 3:
        raise ValueError("At least three grouped folds are required")

    frame = pd.read_csv(args.features, dtype={"genetic_group": str})
    required = {"antibiotic", "label", "genetic_group", "split", "frozen_split"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required feature columns: {sorted(missing)}")
    training = frame[frame["split"].astype(str).str.lower().eq("train")].copy()
    if training.empty:
        raise ValueError("The frozen training partition is empty")
    if not training["frozen_split"].astype(str).str.lower().eq("true").all():
        raise ValueError("Model selection requires a frozen grouped partition")

    marker_columns = sorted(
        column for column in frame.columns if column.startswith("feature__marker__")
    )
    feature_columns = sorted(
        column for column in frame.columns if column.startswith("feature__")
    )
    if not marker_columns or not feature_columns:
        raise ValueError("Marker and full feature matrices are required")

    antibiotics = {}
    for antibiotic, subset in training.groupby("antibiotic", sort=True):
        subset = subset.reset_index(drop=True)
        labels = subset["label"].astype(str).str.lower().map(
            {"susceptible": 0, "resistant": 1}
        )
        if labels.isna().any():
            raise ValueError(f"Unknown labels for {antibiotic}")
        label_values = labels.to_numpy(dtype=int)
        groups = subset["genetic_group"].astype(str).to_numpy()
        splitter = StratifiedGroupKFold(
            n_splits=args.folds,
            shuffle=True,
            random_state=args.random_state,
        )
        folds = []
        for fold, (train_index, validation_index) in enumerate(
            splitter.split(np.zeros(len(subset)), label_values, groups), start=1
        ):
            baseline = _fit_marker_baseline(
                subset.iloc[train_index],
                subset.iloc[validation_index],
                label_values[train_index],
                marker_columns,
                args.random_state,
            )
            candidate = _fit_full_ensemble(
                subset.iloc[train_index],
                subset.iloc[validation_index],
                label_values[train_index],
                feature_columns,
                args.random_state,
            )
            baseline_score = balanced_accuracy_score(
                label_values[validation_index], baseline >= 0.5
            )
            candidate_score = balanced_accuracy_score(
                label_values[validation_index], candidate >= 0.5
            )
            folds.append(
                {
                    "fold": fold,
                    "validation_groups": int(len(set(groups[validation_index]))),
                    "amrfinder_logistic_balanced_accuracy": float(baseline_score),
                    "full_ensemble_balanced_accuracy": float(candidate_score),
                    "delta": float(candidate_score - baseline_score),
                }
            )
        deltas = [item["delta"] for item in folds]
        antibiotics[str(antibiotic)] = {
            "selected_strategy": _strategy(deltas, args.minimum_mean_gain),
            "mean_delta": float(np.mean(deltas)),
            "positive_or_tied_folds": int(sum(delta >= 0 for delta in deltas)),
            "folds": folds,
        }

    payload = {
        "status": "training_groups_only",
        "test_labels_consulted": False,
        "selection_rule": {
            "metric": "balanced_accuracy",
            "minimum_mean_gain": args.minimum_mean_gain,
            "stability": "candidate must tie or improve in all but at most one fold",
        },
        "feature_counts": {
            "amrfinder_markers": len(marker_columns),
            "full": len(feature_columns),
        },
        "antibiotics": antibiotics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
