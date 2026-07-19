import numpy as np
import pytest

from resistsense.modeling import train_model


def test_grouped_training_keeps_groups_disjoint() -> None:
    rng = np.random.default_rng(7)
    groups = np.repeat([f"group-{index}" for index in range(20)], 2)
    labels = np.tile([0, 1], 20)
    signal = labels.reshape(-1, 1) + rng.normal(0, 0.15, size=(40, 1))
    noise = rng.normal(size=(40, 2))
    features = np.hstack([signal, noise])
    bundle = train_model(
        "ampicillin",
        features,
        labels,
        groups,
        ["feature__signal", "feature__noise1", "feature__noise2"],
    )
    assert set(bundle.training_groups).isdisjoint(bundle.calibration_groups)
    assert set(bundle.training_groups).isdisjoint(bundle.test_groups)
    assert set(bundle.calibration_groups).isdisjoint(bundle.test_groups)
    assert set(bundle.probability_calibration_groups).isdisjoint(
        bundle.conformal_groups
    )
    assert set(bundle.estimators) == {
        "logistic_regression",
        "hist_gradient_boosting",
    }
    prediction = bundle.predict(features[:1])
    assert 0 <= prediction.probability_resistant <= 1
    assert 0 <= prediction.ood_score <= 1


def test_fixed_split_is_respected_and_group_leakage_is_rejected() -> None:
    rng = np.random.default_rng(11)
    groups = np.repeat([f"group-{index}" for index in range(20)], 2)
    labels = np.tile([0, 1], 20)
    features = np.column_stack(
        [labels + rng.normal(0, 0.1, len(labels)), rng.normal(size=len(labels))]
    )
    by_group = {
        **{f"group-{index}": "train" for index in range(12)},
        **{f"group-{index}": "calibration" for index in range(12, 16)},
        **{f"group-{index}": "test" for index in range(16, 20)},
    }
    partitions = np.asarray([by_group[group] for group in groups])
    bundle = train_model(
        "ciprofloxacin",
        features,
        labels,
        groups,
        ["signal", "noise"],
        partitions=partitions,
    )
    assert set(bundle.training_groups) == {f"group-{index}" for index in range(12)}
    assert set(bundle.test_groups) == {f"group-{index}" for index in range(16, 20)}

    leaked = partitions.copy()
    leaked[1] = "test"
    with pytest.raises(ValueError, match="cross fixed partitions"):
        train_model(
            "ciprofloxacin",
            features,
            labels,
            groups,
            ["signal", "noise"],
            partitions=leaked,
        )


def test_explicit_probability_and_conformal_splits_are_respected() -> None:
    rng = np.random.default_rng(19)
    groups = np.repeat([f"group-{index}" for index in range(24)], 2)
    labels = np.tile([0, 1], 24)
    features = np.column_stack(
        [labels + rng.normal(0, 0.1, len(labels)), rng.normal(size=len(labels))]
    )
    by_group = {
        **{f"group-{index}": "train" for index in range(12)},
        **{
            f"group-{index}": "probability_calibration"
            for index in range(12, 16)
        },
        **{
            f"group-{index}": "conformal_calibration"
            for index in range(16, 20)
        },
        **{f"group-{index}": "test" for index in range(20, 24)},
    }
    partitions = np.asarray([by_group[group] for group in groups])
    bundle = train_model(
        "ampicillin",
        features,
        labels,
        groups,
        ["signal", "noise"],
        partitions=partitions,
    )
    assert set(bundle.probability_calibration_groups) == {
        f"group-{index}" for index in range(12, 16)
    }
    assert set(bundle.conformal_groups) == {
        f"group-{index}" for index in range(16, 20)
    }


def test_batch_prediction_matches_single_prediction() -> None:
    rng = np.random.default_rng(29)
    features = rng.normal(size=(80, 4))
    labels = np.asarray([index % 2 for index in range(80)])
    groups = np.asarray([f"group-{index}" for index in range(80)])
    bundle = train_model(
        "demo",
        features,
        labels,
        groups,
        ["a", "b", "c", "d"],
    )

    batch = bundle.predict_many(features[:3])
    singles = [bundle.predict(features[index : index + 1]) for index in range(3)]

    for batched, single in zip(batch, singles, strict=True):
        assert batched.probability_resistant == single.probability_resistant
        assert batched.conformal_set == single.conformal_set
        assert batched.ood_score == single.ood_score
        assert batched.model_probabilities == single.model_probabilities


def test_marker_baseline_can_use_one_expert() -> None:
    rng = np.random.default_rng(31)
    features = rng.normal(size=(80, 3))
    labels = np.asarray([index % 2 for index in range(80)])
    groups = np.asarray([f"group-{index}" for index in range(80)])
    bundle = train_model(
        "ampicillin",
        features,
        labels,
        groups,
        ["marker__a", "marker__b", "marker__c"],
        estimator_names=("logistic_regression",),
        strategy="amrfinder_logistic",
    )
    assert bundle.strategy == "amrfinder_logistic"
    assert set(bundle.estimators) == {"logistic_regression"}
    assert set(bundle.predict(features[:1]).model_probabilities) == {
        "logistic_regression"
    }
