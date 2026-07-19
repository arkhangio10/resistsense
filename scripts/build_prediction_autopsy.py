from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


DISCLAIMER = (
    "Research prototype. These held-out cases do not support treatment "
    "recommendations. Standard laboratory testing is required."
)


def _tokens(value: object) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return sorted({token for token in str(value).split("|") if token})


def _case(row: pd.Series, category: str) -> dict:
    truth = str(row["label"]).lower()
    model_label = (
        "resistant" if float(row["probability_resistant"]) >= 0.5 else "susceptible"
    )
    reasons = _tokens(row.get("no_call_reasons"))
    if category == "prevented_error":
        narrative = (
            f"The base classifier predicted {model_label}, while the held-out "
            f"laboratory label was {truth}. The firewall returned no-call because "
            f"of {', '.join(reasons)}, preventing an incorrect emitted result. "
            "Standard laboratory testing is required."
        )
    else:
        narrative = (
            f"The firewall emitted {row['final_status']}, but the held-out "
            f"laboratory label was {truth}. This genuine residual error remains "
            "visible for audit and must not be converted into a treatment claim. "
            "Standard laboratory testing is required."
        )
    expert_probabilities = {
        "logistic_regression": float(row["logistic_probability"]),
    }
    if pd.notna(row.get("hist_gradient_boosting_probability")):
        expert_probabilities["hist_gradient_boosting"] = float(
            row["hist_gradient_boosting_probability"]
        )
    return {
        "case_id": f"{row['antibiotic']}:{row['sample_id']}:{category}",
        "category": category,
        "antibiotic": str(row["antibiotic"]),
        "sample_id": str(row["sample_id"]),
        "genetic_group": str(row["genetic_group"]),
        "laboratory_label": truth,
        "model_label": model_label,
        "probability_resistant": float(row["probability_resistant"]),
        "model_confidence": float(row["model_confidence"]),
        "final_status": str(row["final_status"]),
        "model_strategy": str(row.get("model_strategy", "legacy_full_ensemble")),
        "expert_probabilities": expert_probabilities,
        "model_disagreement": float(row["model_disagreement"]),
        "conformal_set": _tokens(row.get("conformal_set")),
        "ood_score": float(row["ood_score"]),
        "target_status": str(row["target_status"]),
        "known_markers": _tokens(row.get("known_marker_symbols")),
        "no_call_reasons": reasons,
        "narrative": narrative,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build real held-out Prediction Autopsy cases"
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("artifacts/evaluation/predictions.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/prediction_autopsy.json"),
    )
    args = parser.parse_args()

    frame = pd.read_csv(
        args.predictions, dtype={"sample_id": str, "genetic_group": str}
    )
    required = {
        "sample_id",
        "antibiotic",
        "label",
        "genetic_group",
        "split",
        "probability_resistant",
        "logistic_probability",
        "hist_gradient_boosting_probability",
        "model_disagreement",
        "conformal_set",
        "ood_score",
        "target_status",
        "known_marker_symbols",
        "final_status",
        "no_call_reasons",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing autopsy columns: {sorted(missing)}")
    if not frame["split"].astype(str).str.lower().eq("test").all():
        raise ValueError("Prediction Autopsy requires frozen grouped-test rows")

    labels = frame["label"].astype(str).str.lower().map(
        {"susceptible": 0, "resistant": 1}
    )
    if labels.isna().any():
        raise ValueError("Unknown laboratory labels")
    frame["model_label_binary"] = (
        frame["probability_resistant"].to_numpy(dtype=float) >= 0.5
    ).astype(int)
    frame["base_error"] = frame["model_label_binary"].ne(labels)
    frame["emitted"] = frame["final_status"].astype(str).ne("no_call")
    frame["model_confidence"] = frame["probability_resistant"].where(
        frame["model_label_binary"].eq(1),
        1 - frame["probability_resistant"],
    )

    cases = []
    summary = {}
    for antibiotic, subset in frame.groupby("antibiotic", sort=True):
        errors = subset[subset["base_error"]]
        prevented = errors[~errors["emitted"]].sort_values(
            ["model_confidence", "sample_id"], ascending=[False, True]
        )
        escaped = errors[errors["emitted"]].sort_values(
            ["model_confidence", "sample_id"], ascending=[False, True]
        )
        if not prevented.empty:
            cases.append(_case(prevented.iloc[0], "prevented_error"))
        if not escaped.empty:
            cases.append(_case(escaped.iloc[0], "escaped_error"))
        summary[str(antibiotic)] = {
            "test_rows": int(len(subset)),
            "base_errors": int(len(errors)),
            "errors_prevented_by_firewall": int(len(prevented)),
            "errors_escaping_firewall": int(len(escaped)),
            "error_prevention_fraction": (
                float(len(prevented) / len(errors)) if len(errors) else 0.0
            ),
            "firewall_coverage": float(subset["emitted"].mean()),
        }

    payload = {
        "status": "frozen_grouped_test_errors",
        "source": "ResistSense frozen grouped-test predictions",
        "predictions_sha256": hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
        "selection_policy": (
            "For each antibiotic, select the highest-confidence base-model error "
            "blocked by the firewall and the highest-confidence residual emitted "
            "error when one exists."
        ),
        "disclaimer": DISCLAIMER,
        "summary": summary,
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "cases": len(cases),
                "base_errors": sum(item["base_errors"] for item in summary.values()),
                "prevented": sum(
                    item["errors_prevented_by_firewall"]
                    for item in summary.values()
                ),
                "escaped": sum(
                    item["errors_escaping_firewall"] for item in summary.values()
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
