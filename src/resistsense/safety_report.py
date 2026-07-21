from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


LABEL_TO_INT = {"susceptible": 0, "resistant": 1}
EXPECTED_STATUS = {
    "susceptible": "probable_efficacy",
    "resistant": "probable_failure",
}
ALLOWED_STATUSES = {"probable_efficacy", "probable_failure", "no_call"}


def exact_rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
    """Represent every reported rate with its auditable counts."""
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": float(numerator / denominator) if denominator else None,
    }


def _validate_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "sample_id",
        "antibiotic",
        "label",
        "genetic_group",
        "probability_resistant",
        "final_status",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing prediction columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("At least one frozen grouped-test prediction is required")

    normalized = frame.copy()
    normalized["label"] = normalized["label"].astype(str).str.lower()
    normalized["final_status"] = normalized["final_status"].astype(str).str.lower()
    if not normalized["label"].isin(LABEL_TO_INT).all():
        invalid = sorted(set(normalized.loc[~normalized["label"].isin(LABEL_TO_INT), "label"]))
        raise ValueError(f"Unknown laboratory labels: {invalid}")
    if not normalized["final_status"].isin(ALLOWED_STATUSES).all():
        invalid = sorted(
            set(
                normalized.loc[
                    ~normalized["final_status"].isin(ALLOWED_STATUSES),
                    "final_status",
                ]
            )
        )
        raise ValueError(f"Unknown final statuses: {invalid}")
    if "split" in normalized and not normalized["split"].astype(str).str.lower().eq("test").all():
        raise ValueError("Safety report input must contain only frozen grouped-test rows")
    probabilities = pd.to_numeric(normalized["probability_resistant"], errors="coerce")
    if probabilities.isna().any() or not probabilities.between(0, 1).all():
        raise ValueError("probability_resistant must contain values between zero and one")
    normalized["probability_resistant"] = probabilities
    return normalized


def _reason_counts(subset: pd.DataFrame) -> dict[str, int]:
    if "no_call_reasons" not in subset:
        return {}
    reasons: Counter[str] = Counter()
    for value in subset["no_call_reasons"].fillna("").astype(str):
        reasons.update(reason for reason in value.split("|") if reason)
    return dict(sorted(reasons.items()))


def _class_metrics(subset: pd.DataFrame, label: str) -> dict:
    selected = subset[subset["label"].eq(label)]
    emitted = selected["final_status"].ne("no_call")
    correct = selected["final_status"].eq(EXPECTED_STATUS[label])
    incorrect = emitted & ~correct
    total = len(selected)
    emitted_count = int(emitted.sum())
    return {
        "laboratory_class": label,
        "eligible_rows": total,
        "emitted_rows": emitted_count,
        "no_call_rows": int((~emitted).sum()),
        "correct_emitted_rows": int((emitted & correct).sum()),
        "incorrect_emitted_rows": int(incorrect.sum()),
        "coverage": exact_rate(emitted_count, total),
        "selective_accuracy": exact_rate(int((emitted & correct).sum()), emitted_count),
        "residual_error_rate_over_class": exact_rate(int(incorrect.sum()), total),
    }


def _metric_values(subset: pd.DataFrame) -> dict[str, float | None]:
    emitted = subset["final_status"].ne("no_call")
    expected = subset["label"].map(EXPECTED_STATUS)
    incorrect = emitted & subset["final_status"].ne(expected)
    resistant = subset["label"].eq("resistant")
    susceptible = subset["label"].eq("susceptible")

    def ratio(mask: pd.Series, denominator: pd.Series) -> float | None:
        count = int(denominator.sum())
        return float(mask.sum() / count) if count else None

    return {
        "coverage": float(emitted.mean()) if len(subset) else None,
        "resistant_coverage": ratio(emitted & resistant, resistant),
        "susceptible_coverage": ratio(emitted & susceptible, susceptible),
        "residual_error_rate": float(incorrect.mean()) if len(subset) else None,
        "selective_error_rate": ratio(incorrect, emitted),
        "false_susceptibility_signal_rate": ratio(
            resistant & subset["final_status"].eq("probable_efficacy"), resistant
        ),
        "false_resistance_signal_rate": ratio(
            susceptible & subset["final_status"].eq("probable_failure"), susceptible
        ),
    }


def grouped_safety_intervals(
    subset: pd.DataFrame,
    *,
    replicates: int = 1000,
    confidence: float = 0.95,
    random_state: int = 42,
) -> dict[str, dict[str, float | int | None]]:
    """Bootstrap safety metrics by genetic group, never by individual row."""
    if replicates < 1:
        raise ValueError("At least one bootstrap replicate is required")
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between zero and one")
    groups = subset["genetic_group"].astype(str).to_numpy()
    unique_groups = np.unique(groups)
    if len(unique_groups) < 2:
        raise ValueError("At least two genetic groups are required")
    indices = {group: np.flatnonzero(groups == group) for group in unique_groups}
    samples: dict[str, list[float]] = {
        name: [] for name in _metric_values(subset)
    }
    rng = np.random.default_rng(random_state)
    for _ in range(replicates):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        selected_indices = np.concatenate([indices[group] for group in sampled_groups])
        metrics = _metric_values(subset.iloc[selected_indices])
        for name, value in metrics.items():
            if value is not None:
                samples[name].append(value)

    alpha = (1 - confidence) / 2
    estimates = _metric_values(subset)
    return {
        name: {
            "estimate": estimates[name],
            "lower": float(np.quantile(values, alpha)) if values else None,
            "upper": float(np.quantile(values, 1 - alpha)) if values else None,
            "valid_replicates": len(values),
        }
        for name, values in samples.items()
    }


def _base_model_risk_coverage(subset: pd.DataFrame, points: int = 20) -> list[dict]:
    probabilities = subset["probability_resistant"].to_numpy(dtype=float)
    labels = subset["label"].map(LABEL_TO_INT).to_numpy(dtype=int)
    confidence = np.maximum(probabilities, 1 - probabilities)
    correct = (probabilities >= 0.5).astype(int) == labels
    order = np.argsort(-confidence)
    result = []
    for requested in np.linspace(0.05, 1.0, points):
        count = max(1, int(np.ceil(len(subset) * requested)))
        selected = order[:count]
        row = {
            "selected_rows": count,
            "coverage": exact_rate(count, len(subset)),
            "selective_error_rate": exact_rate(int((~correct[selected]).sum()), count),
            "minimum_model_confidence": float(confidence[selected].min()),
            "by_laboratory_class": {},
        }
        for label, encoded in LABEL_TO_INT.items():
            total_class = int((labels == encoded).sum())
            selected_class = selected[labels[selected] == encoded]
            row["by_laboratory_class"][label] = {
                "coverage": exact_rate(len(selected_class), total_class),
                "selective_error_rate": exact_rate(
                    int((~correct[selected_class]).sum()), len(selected_class)
                ),
            }
        result.append(row)
    return result


def _antibiotic_report(
    subset: pd.DataFrame,
    *,
    bootstrap_replicates: int,
    random_state: int,
) -> dict:
    emitted = subset["final_status"].ne("no_call")
    expected = subset["label"].map(EXPECTED_STATUS)
    incorrect = emitted & subset["final_status"].ne(expected)
    base_prediction = np.where(
        subset["probability_resistant"].to_numpy(dtype=float) >= 0.5,
        "resistant",
        "susceptible",
    )
    base_errors = base_prediction != subset["label"].to_numpy(dtype=str)
    false_susceptibility = subset["label"].eq("resistant") & subset[
        "final_status"
    ].eq("probable_efficacy")
    false_resistance = subset["label"].eq("susceptible") & subset[
        "final_status"
    ].eq("probable_failure")

    return {
        "rows": len(subset),
        "unique_genomes": int(subset["sample_id"].astype(str).nunique()),
        "genetic_groups": int(subset["genetic_group"].astype(str).nunique()),
        "model_strategy": (
            str(subset["model_strategy"].iloc[0])
            if "model_strategy" in subset
            else "not_recorded"
        ),
        "decision_counts": {
            str(status): int(count)
            for status, count in sorted(subset["final_status"].value_counts().items())
        },
        "overall": {
            "coverage": exact_rate(int(emitted.sum()), len(subset)),
            "no_call_rate": exact_rate(int((~emitted).sum()), len(subset)),
            "selective_accuracy": exact_rate(
                int((emitted & ~incorrect).sum()), int(emitted.sum())
            ),
            "residual_error_rate": exact_rate(int(incorrect.sum()), len(subset)),
        },
        "by_laboratory_class": {
            label: _class_metrics(subset, label) for label in LABEL_TO_INT
        },
        "harm_specific_residuals": {
            "false_susceptibility_signal": exact_rate(
                int(false_susceptibility.sum()), int(subset["label"].eq("resistant").sum())
            ),
            "false_resistance_signal": exact_rate(
                int(false_resistance.sum()), int(subset["label"].eq("susceptible").sum())
            ),
        },
        "base_model_errors": {
            "total": int(base_errors.sum()),
            "prevented_by_firewall": int((base_errors & ~emitted.to_numpy()).sum()),
            "escaping_firewall": int((base_errors & emitted.to_numpy()).sum()),
        },
        "no_call_reasons": _reason_counts(subset),
        "grouped_bootstrap_95pct": grouped_safety_intervals(
            subset,
            replicates=bootstrap_replicates,
            confidence=0.95,
            random_state=random_state,
        ),
        "base_model_risk_coverage_curve": _base_model_risk_coverage(subset),
    }


def build_class_aware_safety_report(
    frame: pd.DataFrame,
    *,
    predictions_sha256: str,
    bootstrap_replicates: int = 1000,
    random_state: int = 42,
) -> dict:
    normalized = _validate_predictions(frame)
    antibiotics = {
        str(antibiotic): _antibiotic_report(
            subset.reset_index(drop=True),
            bootstrap_replicates=bootstrap_replicates,
            random_state=random_state,
        )
        for antibiotic, subset in normalized.groupby("antibiotic", sort=True)
    }
    return {
        "schema_version": "1.0",
        "status": "frozen_internal_grouped_validation",
        "research_demo_status": "pass",
        "clinical_release_status": "fail_not_externally_validated",
        "clinical_release_reasons": [
            "independent_external_validation_incomplete",
            "research_prototype_not_a_diagnostic_device",
        ],
        "source": "ResistSense frozen grouped-test predictions",
        "predictions_sha256": predictions_sha256,
        "evaluation_scope": {
            "species": "Escherichia coli",
            "split": "frozen_grouped_test",
            "rows": len(normalized),
            "unique_genomes": int(normalized["sample_id"].astype(str).nunique()),
            "antibiotics": len(antibiotics),
            "external_validation_complete": False,
            "test_set_retuning_allowed": False,
        },
        "limitations": [
            "Metrics are internal and were measured on an already inspected frozen test set.",
            "Coverage is asymmetric by laboratory class and must not be hidden by aggregate accuracy.",
            "An independent overlap-free external cohort is required before any clinical claim.",
            "Every emitted result still requires standard laboratory antimicrobial-susceptibility testing.",
        ],
        "antibiotics": antibiotics,
    }


def report_from_csv(
    path: Path,
    *,
    bootstrap_replicates: int = 1000,
    random_state: int = 42,
) -> dict:
    return build_class_aware_safety_report(
        pd.read_csv(path),
        predictions_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        bootstrap_replicates=bootstrap_replicates,
        random_state=random_state,
    )


def render_markdown(report: dict) -> str:
    lines = [
        "# ResistSense class-aware safety report",
        "",
        "> Internal research validation only. This is not a clinical release and does not recommend treatment. Standard laboratory antimicrobial-susceptibility testing is required.",
        "",
        f"- Research demo status: `{report['research_demo_status']}`",
        f"- Clinical release status: `{report['clinical_release_status']}`",
        f"- Frozen prediction SHA-256: `{report['predictions_sha256']}`",
        "- Test-set retuning allowed: `false`",
        "",
        "## Class-specific coverage and residual errors",
        "",
        "| Antibiotic | R coverage | S coverage | Incorrect emitted R-class signals | Incorrect emitted S-class signals |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for antibiotic, payload in report["antibiotics"].items():
        resistant = payload["by_laboratory_class"]["resistant"]
        susceptible = payload["by_laboratory_class"]["susceptible"]
        r_coverage = resistant["coverage"]
        s_coverage = susceptible["coverage"]
        lines.append(
            "| "
            + " | ".join(
                [
                    antibiotic,
                    f"{100 * r_coverage['value']:.1f}% ({r_coverage['numerator']}/{r_coverage['denominator']})",
                    f"{100 * s_coverage['value']:.1f}% ({s_coverage['numerator']}/{s_coverage['denominator']})",
                    f"{resistant['incorrect_emitted_rows']}/{resistant['eligible_rows']}",
                    f"{susceptible['incorrect_emitted_rows']}/{susceptible['eligible_rows']}",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "The JSON artifact also contains genetic-group bootstrap intervals, exact numerators and denominators, no-call reasons, harm-specific residual rates, and class-aware base-model risk/coverage curves.",
            "",
            "## Interpretation boundary",
            "",
            "High selective accuracy does not imply uniform usefulness. Endpoints with low resistant-class coverage are abstention-dominant for that class. The frozen test set has already been inspected and will not be used for further threshold or model tuning. Independent, overlap-free external validation remains future work.",
            "",
        ]
    )
    return "\n".join(lines)
