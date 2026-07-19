from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _optional_rank_metric(metric, labels: np.ndarray, probabilities: np.ndarray):
    return float(metric(labels, probabilities)) if len(np.unique(labels)) == 2 else None


def standard_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> dict[str, float | int | list[list[int]] | None]:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predicted = (probabilities >= 0.5).astype(int)
    return {
        "balanced_accuracy": float(balanced_accuracy_score(labels, predicted)),
        "recall_resistant": float(recall_score(labels, predicted, pos_label=1)),
        "recall_susceptible": float(recall_score(labels, predicted, pos_label=0)),
        "precision_resistant": float(
            precision_score(labels, predicted, pos_label=1, zero_division=0)
        ),
        "f1_resistant": float(f1_score(labels, predicted, pos_label=1)),
        "auroc": _optional_rank_metric(roc_auc_score, labels, probabilities),
        "pr_auc": _optional_rank_metric(average_precision_score, labels, probabilities),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "confusion_matrix_tn_fp_fn_tp": confusion_matrix(
            labels, predicted, labels=[0, 1]
        ).tolist(),
    }


def reliability_bins(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    bins: int = 10,
) -> list[dict[str, float | int | None]]:
    edges = np.linspace(0, 1, bins + 1)
    result = []
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        selected = (probabilities >= lower) & (
            probabilities <= upper if index == bins - 1 else probabilities < upper
        )
        result.append(
            {
                "lower": float(lower),
                "upper": float(upper),
                "count": int(selected.sum()),
                "mean_probability": (
                    float(probabilities[selected].mean()) if selected.any() else None
                ),
                "observed_resistant_rate": (
                    float(labels[selected].mean()) if selected.any() else None
                ),
            }
        )
    return result


def calibration_errors(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    bins: int = 10,
) -> dict[str, float]:
    reliability = reliability_bins(labels, probabilities, bins=bins)
    total = sum(item["count"] for item in reliability)
    if total == 0:
        raise ValueError("At least one calibration sample is required")
    gaps = [
        abs(item["mean_probability"] - item["observed_resistant_rate"])
        if item["count"]
        else 0.0
        for item in reliability
    ]
    return {
        "expected_calibration_error": float(
            sum(item["count"] * gap for item, gap in zip(reliability, gaps, strict=True))
            / total
        ),
        "maximum_calibration_error": float(max(gaps)),
    }


def conformal_metrics(
    labels: np.ndarray,
    prediction_sets: list[set[str]],
) -> dict[str, float]:
    labels = np.asarray(labels, dtype=int)
    if len(labels) != len(prediction_sets):
        raise ValueError("Labels and conformal sets must have equal lengths")
    if not len(labels):
        raise ValueError("At least one conformal sample is required")
    expected = np.asarray(
        ["resistant" if label == 1 else "susceptible" for label in labels]
    )
    covered = np.asarray(
        [label in prediction_set for label, prediction_set in zip(
            expected, prediction_sets, strict=True
        )],
        dtype=bool,
    )
    sizes = np.asarray([len(prediction_set) for prediction_set in prediction_sets])
    return {
        "empirical_coverage": float(covered.mean()),
        "singleton_rate": float((sizes == 1).mean()),
        "empty_rate": float((sizes == 0).mean()),
        "ambiguous_rate": float((sizes > 1).mean()),
        "mean_set_size": float(sizes.mean()),
    }


def grouped_bootstrap_intervals(
    labels: np.ndarray,
    probabilities: np.ndarray,
    groups: np.ndarray,
    *,
    replicates: int = 1000,
    confidence: float = 0.95,
    random_state: int = 42,
) -> dict[str, dict[str, float | int]]:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    groups = np.asarray(groups, dtype=str)
    if not (len(labels) == len(probabilities) == len(groups)):
        raise ValueError("Labels, probabilities, and groups must have equal lengths")
    if replicates < 1:
        raise ValueError("At least one bootstrap replicate is required")
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between zero and one")
    unique_groups = np.unique(groups)
    if len(unique_groups) < 2:
        raise ValueError("At least two genetic groups are required")

    indices_by_group = {
        group: np.flatnonzero(groups == group) for group in unique_groups
    }
    rng = np.random.default_rng(random_state)
    values: dict[str, list[float]] = {
        "balanced_accuracy": [],
        "auroc": [],
        "pr_auc": [],
        "brier_score": [],
    }
    for _ in range(replicates):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        selected = np.concatenate([indices_by_group[group] for group in sampled_groups])
        sampled_labels = labels[selected]
        sampled_probabilities = probabilities[selected]
        if len(np.unique(sampled_labels)) < 2:
            continue
        metrics = standard_metrics(sampled_labels, sampled_probabilities)
        for name in values:
            value = metrics[name]
            if value is not None:
                values[name].append(float(value))

    alpha = (1 - confidence) / 2
    estimates = standard_metrics(labels, probabilities)
    intervals = {}
    for name, samples in values.items():
        if not samples:
            raise ValueError(f"No valid bootstrap replicates for {name}")
        intervals[name] = {
            "estimate": float(estimates[name]),
            "lower": float(np.quantile(samples, alpha)),
            "upper": float(np.quantile(samples, 1 - alpha)),
            "valid_replicates": len(samples),
        }
    return intervals


def risk_coverage_curve(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    points: int = 20,
) -> list[dict[str, float]]:
    confidence = np.maximum(probabilities, 1 - probabilities)
    correct = ((probabilities >= 0.5).astype(int) == labels).astype(float)
    order = np.argsort(-confidence)
    result = []
    for coverage in np.linspace(0.05, 1.0, points):
        count = max(1, int(np.ceil(len(labels) * coverage)))
        selected = order[:count]
        result.append(
            {
                "coverage": float(count / len(labels)),
                "selective_risk": float(1 - correct[selected].mean()),
                "minimum_confidence": float(confidence[selected].min()),
            }
        )
    return result


def firewall_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    emitted: np.ndarray,
    groups: np.ndarray,
    *,
    ood_scores: np.ndarray | None = None,
    high_confidence_threshold: float = 0.90,
    ood_threshold: float = 0.80,
    explanation_concordant: np.ndarray | None = None,
) -> dict:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    emitted = np.asarray(emitted, dtype=bool)
    groups = np.asarray(groups, dtype=str)
    if not (len(labels) == len(probabilities) == len(emitted) == len(groups)):
        raise ValueError("All evaluation arrays must have equal lengths")
    if len(labels) == 0:
        raise ValueError("At least one evaluation sample is required")

    predicted = (probabilities >= 0.5).astype(int)
    correct = predicted == labels
    confidence = np.maximum(probabilities, 1 - probabilities)
    base_errors = ~correct
    group_accuracy = {
        group: float(correct[(groups == group) & emitted].mean())
        for group in sorted(set(groups))
        if ((groups == group) & emitted).any()
    }
    output = {
        "samples": int(len(labels)),
        "coverage": float(emitted.mean()),
        "no_call_rate": float((~emitted).mean()),
        "selective_accuracy": float(correct[emitted].mean()) if emitted.any() else None,
        "unsafe_confidence_rate": float(
            (base_errors & (confidence >= high_confidence_threshold)).mean()
        ),
        "errors_prevented_by_firewall_count": int((base_errors & ~emitted).sum()),
        "errors_prevented_by_firewall_fraction": (
            float((base_errors & ~emitted).sum() / base_errors.sum())
            if base_errors.any()
            else 0.0
        ),
        "worst_group_selective_accuracy": min(group_accuracy.values())
        if group_accuracy
        else None,
        "group_selective_accuracy": group_accuracy,
        "risk_coverage_curve": risk_coverage_curve(labels, probabilities),
    }
    if ood_scores is not None:
        ood_scores = np.asarray(ood_scores, dtype=float)
        if len(ood_scores) != len(labels):
            raise ValueError("OOD scores must match evaluation sample count")
        ood = ood_scores > ood_threshold
        output["ood_samples"] = int(ood.sum())
        output["ood_failure_rate"] = (
            float((base_errors & emitted)[ood].mean()) if ood.any() else None
        )
    if explanation_concordant is not None:
        explanation_concordant = np.asarray(explanation_concordant, dtype=bool)
        if len(explanation_concordant) != len(labels):
            raise ValueError("Explanation flags must match evaluation sample count")
        output["explanation_concordance"] = float(explanation_concordant.mean())
    return output
