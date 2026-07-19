from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from .evaluation import standard_metrics


@dataclass
class ModelPrediction:
    probability_resistant: float
    conformal_set: set[str]
    ood_score: float
    model_probabilities: dict[str, float]


@dataclass
class ModelBundle:
    antibiotic: str
    feature_names: list[str]
    scaler: StandardScaler
    estimators: dict[str, Any]
    calibrator: LogisticRegression
    neighbors: NearestNeighbors
    calibration_distances: np.ndarray
    conformal_quantile: float
    alpha: float
    metrics: dict[str, Any]
    training_groups: list[str]
    probability_calibration_groups: list[str]
    conformal_groups: list[str]
    calibration_groups: list[str]
    test_groups: list[str]
    strategy: str = "full_ensemble"
    dataset_sha256: str | None = None

    def predict(self, raw_features: np.ndarray) -> ModelPrediction:
        predictions = self.predict_many(raw_features)
        if len(predictions) != 1:
            raise ValueError("predict expects exactly one feature row")
        return predictions[0]

    def predict_many(self, raw_features: np.ndarray) -> list[ModelPrediction]:
        if raw_features.ndim != 2:
            raise ValueError("Feature input must be a two-dimensional matrix")
        if raw_features.shape[1] != len(self.feature_names):
            raise ValueError("Feature matrix shape does not match feature names")
        scaled = self.scaler.transform(raw_features)
        expert_probability_arrays = {
            name: estimator.predict_proba(scaled)[:, 1]
            for name, estimator in self.estimators.items()
        }
        raw_ensemble = np.column_stack(
            list(expert_probability_arrays.values())
        ).mean(axis=1)
        scores = _logit(raw_ensemble).reshape(-1, 1)
        probabilities = self.calibrator.predict_proba(scores)[:, 1]
        distances = self.neighbors.kneighbors(scaled, n_neighbors=1)[0][:, 0]
        if len(self.calibration_distances):
            ranks = np.searchsorted(
                self.calibration_distances, distances, side="right"
            )
            ood_scores = ranks / len(self.calibration_distances)
        else:
            ood_scores = np.ones(len(probabilities), dtype=float)

        predictions = []
        for index, probability in enumerate(probabilities):
            probability = float(probability)
            label_probabilities = {
                "susceptible": 1 - probability,
                "resistant": probability,
            }
            conformal = {
                label
                for label, label_probability in label_probabilities.items()
                if 1 - label_probability <= self.conformal_quantile
            }
            predictions.append(
                ModelPrediction(
                    probability_resistant=probability,
                    conformal_set=conformal,
                    ood_score=float(ood_scores[index]),
                    model_probabilities={
                        name: float(values[index])
                        for name, values in expert_probability_arrays.items()
                    },
                )
            )
        return predictions


def _group_splits(
    groups: np.ndarray,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    indices = np.arange(len(groups))
    first = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=random_state)
    train_cal, test = next(first.split(indices, groups=groups))
    second = GroupShuffleSplit(
        n_splits=1,
        test_size=0.25,
        random_state=random_state + 1,
    )
    train_rel, calibration_pool_rel = next(
        second.split(train_cal, groups=groups[train_cal])
    )
    calibration_pool = train_cal[calibration_pool_rel]
    third = GroupShuffleSplit(
        n_splits=1,
        test_size=0.50,
        random_state=random_state + 2,
    )
    probability_rel, conformal_rel = next(
        third.split(calibration_pool, groups=groups[calibration_pool])
    )
    return (
        train_cal[train_rel],
        calibration_pool[probability_rel],
        calibration_pool[conformal_rel],
        test,
    )


def _fixed_group_splits(
    groups: np.ndarray,
    partitions: np.ndarray,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    normalized = np.char.lower(partitions.astype(str))
    train = np.flatnonzero(normalized == "train")
    test = np.flatnonzero(normalized == "test")

    group_partitions: dict[str, set[str]] = {}
    for group, partition in zip(groups.astype(str), normalized, strict=True):
        group_partitions.setdefault(group, set()).add(str(partition))
    leaked = sorted(group for group, values in group_partitions.items() if len(values) > 1)
    if leaked:
        raise ValueError(f"Genetic groups cross fixed partitions: {leaked[:5]}")

    probability = np.flatnonzero(normalized == "probability_calibration")
    conformal = np.flatnonzero(normalized == "conformal_calibration")
    if len(probability) or len(conformal):
        if not len(train) or not len(probability) or not len(conformal) or not len(test):
            raise ValueError(
                "Explicit fixed split must contain train, probability_calibration, "
                "conformal_calibration, and test"
            )
        return train, probability, conformal, test

    calibration_pool = np.flatnonzero(normalized == "calibration")
    if not len(train) or not len(calibration_pool) or not len(test):
        raise ValueError("Fixed split must contain train, calibration, and test")

    divider = GroupShuffleSplit(
        n_splits=1,
        test_size=0.50,
        random_state=random_state + 2,
    )
    probability_rel, conformal_rel = next(
        divider.split(calibration_pool, groups=groups[calibration_pool])
    )
    return (
        train,
        calibration_pool[probability_rel],
        calibration_pool[conformal_rel],
        test,
    )


def _require_both_classes(name: str, labels: np.ndarray) -> None:
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError(f"{name} split must contain resistant and susceptible labels")


def _conformal_quantile(
    probabilities: np.ndarray,
    labels: np.ndarray,
    alpha: float,
) -> float:
    true_probability = np.where(labels == 1, probabilities, 1 - probabilities)
    scores = 1 - true_probability
    level = min(1.0, np.ceil((len(scores) + 1) * (1 - alpha)) / len(scores))
    return float(np.quantile(scores, level, method="higher"))


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped))


def _raw_ensemble_probabilities(
    estimators: dict[str, Any],
    features: np.ndarray,
) -> np.ndarray:
    matrix = np.column_stack(
        [estimator.predict_proba(features)[:, 1] for estimator in estimators.values()]
    )
    return matrix.mean(axis=1)


def train_model(
    antibiotic: str,
    features: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    feature_names: list[str],
    *,
    alpha: float = 0.10,
    random_state: int = 42,
    dataset_sha256: str | None = None,
    partitions: np.ndarray | None = None,
    estimator_names: tuple[str, ...] = (
        "logistic_regression",
        "hist_gradient_boosting",
    ),
    strategy: str = "full_ensemble",
) -> ModelBundle:
    if len(features) != len(labels) or len(labels) != len(groups):
        raise ValueError("Features, labels, and groups must have equal lengths")
    if len(set(groups.tolist())) < 10:
        raise ValueError("At least ten genetic groups are required")
    if features.ndim != 2 or features.shape[1] != len(feature_names):
        raise ValueError("Feature matrix shape does not match feature names")
    if partitions is not None and len(partitions) != len(labels):
        raise ValueError("Partitions must match labels")

    train_idx, probability_idx, conformal_idx, test_idx = (
        _fixed_group_splits(groups, partitions, random_state)
        if partitions is not None
        else _group_splits(groups, random_state)
    )
    for name, idx in (
        ("training", train_idx),
        ("probability calibration", probability_idx),
        ("conformal calibration", conformal_idx),
        ("test", test_idx),
    ):
        _require_both_classes(name, labels[idx])

    scaler = StandardScaler().fit(features[train_idx])
    train_scaled = scaler.transform(features[train_idx])
    probability_scaled = scaler.transform(features[probability_idx])
    conformal_scaled = scaler.transform(features[conformal_idx])
    test_scaled = scaler.transform(features[test_idx])

    available_estimators: dict[str, Any] = {
        "logistic_regression": LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=random_state,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=150,
            learning_rate=0.06,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=random_state,
        ),
    }
    unknown_estimators = sorted(set(estimator_names).difference(available_estimators))
    if unknown_estimators:
        raise ValueError(f"Unknown estimator names: {unknown_estimators}")
    if not estimator_names:
        raise ValueError("At least one estimator is required")
    estimators = {
        name: available_estimators[name]
        for name in estimator_names
    }
    for estimator in estimators.values():
        estimator.fit(train_scaled, labels[train_idx])

    probability_raw = _raw_ensemble_probabilities(estimators, probability_scaled)
    probability_scores = _logit(probability_raw).reshape(-1, 1)
    calibrator = LogisticRegression(random_state=random_state).fit(
        probability_scores,
        labels[probability_idx],
    )
    conformal_raw = _raw_ensemble_probabilities(estimators, conformal_scaled)
    conformal_probabilities = calibrator.predict_proba(
        _logit(conformal_raw).reshape(-1, 1)
    )[:, 1]
    conformal_quantile = _conformal_quantile(
        conformal_probabilities,
        labels[conformal_idx],
        alpha,
    )

    neighbors = NearestNeighbors(n_neighbors=1).fit(train_scaled)
    calibration_distances = np.sort(
        neighbors.kneighbors(conformal_scaled, n_neighbors=1)[0][:, 0]
    )
    test_raw = _raw_ensemble_probabilities(estimators, test_scaled)
    test_probabilities = calibrator.predict_proba(
        _logit(test_raw).reshape(-1, 1)
    )[:, 1]

    probability_groups = sorted(set(groups[probability_idx].astype(str)))
    conformal_groups = sorted(set(groups[conformal_idx].astype(str)))

    return ModelBundle(
        antibiotic=antibiotic,
        feature_names=feature_names,
        scaler=scaler,
        estimators=estimators,
        calibrator=calibrator,
        neighbors=neighbors,
        calibration_distances=calibration_distances,
        conformal_quantile=conformal_quantile,
        alpha=alpha,
        metrics=standard_metrics(labels[test_idx], test_probabilities),
        training_groups=sorted(set(groups[train_idx].astype(str))),
        probability_calibration_groups=probability_groups,
        conformal_groups=conformal_groups,
        calibration_groups=sorted(set(probability_groups + conformal_groups)),
        test_groups=sorted(set(groups[test_idx].astype(str))),
        strategy=strategy,
        dataset_sha256=dataset_sha256,
    )


def save_model(bundle: ModelBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def load_model(path: Path) -> ModelBundle:
    bundle = joblib.load(path)
    if not isinstance(bundle, ModelBundle):
        raise TypeError(f"Unexpected model artifact type: {type(bundle)!r}")
    return bundle
