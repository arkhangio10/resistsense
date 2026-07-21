import pandas as pd
import pytest

from resistsense.safety_report import build_class_aware_safety_report, exact_rate


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sample_id": ["r1", "r2", "s1", "s2"],
            "antibiotic": ["example"] * 4,
            "label": ["resistant", "resistant", "susceptible", "susceptible"],
            "genetic_group": ["g1", "g2", "g3", "g4"],
            "split": ["test"] * 4,
            "probability_resistant": [0.9, 0.8, 0.1, 0.9],
            "final_status": [
                "probable_failure",
                "no_call",
                "probable_efficacy",
                "probable_failure",
            ],
            "no_call_reasons": ["", "out_of_distribution", "", ""],
            "model_strategy": ["amrfinder_logistic"] * 4,
        }
    )


def test_exact_rate_keeps_numerator_and_denominator() -> None:
    assert exact_rate(1, 4) == {"numerator": 1, "denominator": 4, "value": 0.25}
    assert exact_rate(0, 0)["value"] is None


def test_report_exposes_class_asymmetry_and_residual_harms() -> None:
    report = build_class_aware_safety_report(
        _frame(),
        predictions_sha256="abc",
        bootstrap_replicates=20,
        random_state=7,
    )
    payload = report["antibiotics"]["example"]
    assert payload["by_laboratory_class"]["resistant"]["coverage"] == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
    }
    assert payload["by_laboratory_class"]["susceptible"]["coverage"]["value"] == 1.0
    assert payload["harm_specific_residuals"]["false_resistance_signal"] == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
    }
    assert payload["no_call_reasons"] == {"out_of_distribution": 1}
    assert report["research_demo_status"] == "pass"
    assert report["clinical_release_status"] == "fail_not_externally_validated"
    assert report["evaluation_scope"]["test_set_retuning_allowed"] is False


def test_report_rejects_non_test_rows() -> None:
    frame = _frame()
    frame.loc[0, "split"] = "train"
    with pytest.raises(ValueError, match="only frozen grouped-test"):
        build_class_aware_safety_report(
            frame,
            predictions_sha256="abc",
            bootstrap_replicates=5,
        )
