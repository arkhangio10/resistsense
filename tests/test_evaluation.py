import numpy as np

from resistsense.evaluation import (
    calibration_errors,
    conformal_metrics,
    firewall_metrics,
    grouped_bootstrap_intervals,
    reliability_bins,
    standard_metrics,
)


def test_firewall_metrics_measure_abstention_and_prevented_errors() -> None:
    labels = np.asarray([0, 1, 1, 0])
    probabilities = np.asarray([0.1, 0.9, 0.1, 0.8])
    emitted = np.asarray([True, True, False, False])
    groups = np.asarray(["a", "b", "c", "d"])
    result = firewall_metrics(labels, probabilities, emitted, groups)
    assert result["coverage"] == 0.5
    assert result["selective_accuracy"] == 1.0
    assert result["errors_prevented_by_firewall_count"] == 2


def test_standard_and_reliability_outputs_are_complete() -> None:
    labels = np.asarray([0, 0, 1, 1])
    probabilities = np.asarray([0.1, 0.2, 0.8, 0.9])
    metrics = standard_metrics(labels, probabilities)
    assert metrics["balanced_accuracy"] == 1.0
    assert metrics["confusion_matrix_tn_fp_fn_tp"] == [[2, 0], [0, 2]]
    assert sum(item["count"] for item in reliability_bins(labels, probabilities)) == 4


def test_calibration_conformal_and_grouped_bootstrap_outputs() -> None:
    labels = np.asarray([0, 1, 0, 1, 0, 1, 0, 1])
    probabilities = np.asarray([0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6])
    groups = np.asarray(["a", "a", "b", "b", "c", "c", "d", "d"])
    prediction_sets = [
        {"susceptible"} if label == 0 else {"resistant"} for label in labels
    ]

    calibration = calibration_errors(labels, probabilities)
    conformal = conformal_metrics(labels, prediction_sets)
    intervals = grouped_bootstrap_intervals(
        labels, probabilities, groups, replicates=25, random_state=7
    )

    assert calibration["expected_calibration_error"] >= 0
    assert conformal["empirical_coverage"] == 1.0
    assert conformal["singleton_rate"] == 1.0
    assert intervals["balanced_accuracy"]["valid_replicates"] == 25
