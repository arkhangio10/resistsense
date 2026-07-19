from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from resistsense.evaluation import (
    calibration_errors,
    conformal_metrics,
    firewall_metrics,
    grouped_bootstrap_intervals,
    reliability_bins,
    standard_metrics,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate ResistSense predictions by antibiotic and genetic group"
    )
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/evaluation.json"),
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    frame = pd.read_csv(args.predictions)
    required = {
        "antibiotic",
        "label",
        "probability_resistant",
        "final_status",
        "genetic_group",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing prediction columns: {sorted(missing)}")
    if "split" in frame and not frame["split"].astype(str).str.lower().eq("test").all():
        raise ValueError("Evaluation input must contain only frozen grouped-test rows")

    report = {}
    for antibiotic, subset in frame.groupby("antibiotic"):
        labels = subset["label"].astype(str).str.lower().map(
            {"susceptible": 0, "resistant": 1}
        )
        if labels.isna().any():
            raise ValueError(f"Unknown labels for {antibiotic}")
        label_values = labels.to_numpy(dtype=int)
        probabilities = subset["probability_resistant"].to_numpy(dtype=float)
        emitted = subset["final_status"].astype(str).ne("no_call").to_numpy()
        groups = subset["genetic_group"].astype(str).to_numpy()
        options = {}
        if "ood_score" in subset:
            options["ood_scores"] = subset["ood_score"].to_numpy(dtype=float)
        if "explanation_concordant" in subset:
            options["explanation_concordant"] = (
                subset["explanation_concordant"].astype(bool).to_numpy()
            )
        conformal_sets = [
            set(str(value).split("|"))
            if pd.notna(value) and str(value).strip()
            else set()
            for value in subset.get("conformal_set", pd.Series([""] * len(subset)))
        ]
        decisions = {
            str(status): int(count)
            for status, count in subset["final_status"].value_counts().items()
        }
        reasons = (
            subset.get("no_call_reasons", pd.Series([""] * len(subset)))
            .fillna("")
            .astype(str)
            .str.split("|")
            .explode()
        )
        reasons = reasons[reasons.ne("")]
        experts = {}
        for column, name in (
            ("logistic_probability", "logistic_regression"),
            ("hist_gradient_boosting_probability", "hist_gradient_boosting"),
        ):
            if column in subset and subset[column].notna().all():
                experts[name] = standard_metrics(
                    label_values, subset[column].to_numpy(dtype=float)
                )
        report[str(antibiotic)] = {
            "model_strategy": (
                str(subset["model_strategy"].iloc[0])
                if "model_strategy" in subset
                else "legacy_full_ensemble"
            ),
            "conformal_alpha": (
                float(subset["conformal_alpha"].iloc[0])
                if "conformal_alpha" in subset
                else None
            ),
            "standard": standard_metrics(label_values, probabilities),
            "bootstrap_95pct": grouped_bootstrap_intervals(
                label_values,
                probabilities,
                groups,
                replicates=args.bootstrap_replicates,
                random_state=args.random_state,
            ),
            "experts": experts,
            "calibration": {
                **calibration_errors(label_values, probabilities),
                "reliability_bins": reliability_bins(label_values, probabilities),
            },
            "conformal": conformal_metrics(label_values, conformal_sets),
            "decisions": decisions,
            "no_call_reasons": {
                str(reason): int(count) for reason, count in reasons.value_counts().items()
            },
            "firewall": firewall_metrics(
                label_values,
                probabilities,
                emitted,
                groups,
                **options,
            ),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "predictions_sha256": hashlib.sha256(
                    args.predictions.read_bytes()
                ).hexdigest(),
                "bootstrap_replicates": args.bootstrap_replicates,
                "antibiotics": report,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "antibiotics": len(report)}, indent=2))


if __name__ == "__main__":
    main()
