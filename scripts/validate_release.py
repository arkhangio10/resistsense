"""Validate the machine-readable safety gates for a ResistSense release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from resistsense.config import load_config
from resistsense.model_store import artifact_name
from resistsense.modeling import load_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a ResistSense release candidate")
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/features/resistsense_features.csv"),
    )
    parser.add_argument(
        "--model-dir", type=Path, default=Path("artifacts/runtime/models")
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("artifacts/evaluation/predictions.csv"),
    )
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=Path("artifacts/evaluation/evaluation.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/release_gate.json"),
    )
    parser.add_argument("--minimum-conformal-coverage", type=float, default=0.90)
    parser.add_argument("--minimum-selective-accuracy", type=float, default=0.95)
    args = parser.parse_args()

    config = load_config()
    dataset_sha256 = hashlib.sha256(args.features.read_bytes()).hexdigest()
    predictions_sha256 = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    predictions = pd.read_csv(args.predictions)
    evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, evidence: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    check(
        "evaluation_prediction_hash",
        evaluation.get("predictions_sha256") == predictions_sha256,
        predictions_sha256,
    )
    check(
        "frozen_test_only",
        predictions["split"].astype(str).str.lower().eq("test").all(),
        sorted(predictions["split"].astype(str).unique().tolist()),
    )
    check(
        "independent_targets_available",
        predictions["target_annotation_available"].astype(bool).all(),
        int((~predictions["target_annotation_available"].astype(bool)).sum()),
    )
    check(
        "explanations_require_laboratory_confirmation",
        predictions["explanation_concordant"].astype(bool).all(),
        int((~predictions["explanation_concordant"].astype(bool)).sum()),
    )

    for antibiotic in config.scope.antibiotics:
        policy = config.modeling.antibiotics[antibiotic]
        bundle = load_model(args.model_dir / artifact_name(antibiotic))
        subset = predictions[predictions["antibiotic"].astype(str).eq(antibiotic)]
        metrics = evaluation["antibiotics"][antibiotic]
        check(
            f"{antibiotic}:dataset_hash",
            bundle.dataset_sha256 == dataset_sha256,
            bundle.dataset_sha256,
        )
        check(
            f"{antibiotic}:strategy",
            bundle.strategy == policy.strategy
            and subset["model_strategy"].astype(str).eq(policy.strategy).all(),
            bundle.strategy,
        )
        check(
            f"{antibiotic}:conformal_alpha",
            bundle.alpha == policy.conformal_alpha
            and subset["conformal_alpha"].astype(float).eq(policy.conformal_alpha).all(),
            bundle.alpha,
        )
        check(
            f"{antibiotic}:test_rows",
            len(subset) == 437,
            len(subset),
        )
        conformal_coverage = float(metrics["conformal"]["empirical_coverage"])
        check(
            f"{antibiotic}:conformal_coverage",
            conformal_coverage >= args.minimum_conformal_coverage,
            conformal_coverage,
        )
        selective_accuracy = metrics["firewall"]["selective_accuracy"]
        check(
            f"{antibiotic}:selective_accuracy",
            selective_accuracy is None
            or float(selective_accuracy) >= args.minimum_selective_accuracy,
            selective_accuracy,
        )

    failed = [item for item in checks if not item["passed"]]
    payload = {
        "status": "pass" if not failed else "fail",
        "research_use_only": True,
        "external_validation_complete": False,
        "dataset_sha256": dataset_sha256,
        "predictions_sha256": predictions_sha256,
        "thresholds": {
            "minimum_conformal_coverage": args.minimum_conformal_coverage,
            "minimum_selective_accuracy": args.minimum_selective_accuracy,
        },
        "checks": checks,
        "failed_checks": [item["name"] for item in failed],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
