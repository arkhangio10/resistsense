from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from resistsense.config import load_config
from resistsense.model_store import artifact_name
from resistsense.modeling import save_model, train_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train grouped, calibrated ResistSense logistic baselines"
    )
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/runtime/models"))
    parser.add_argument(
        "--allow-provisional-split",
        action="store_true",
        help="Research-only override for an unfrozen random development split",
    )
    args = parser.parse_args()
    config = load_config()
    selection_path = config.modeling.selection_source
    if not selection_path.is_file():
        raise ValueError(
            "Training-only model-selection evidence is unavailable. Run "
            "scripts/select_model_strategy.py first."
        )
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("test_labels_consulted") is not False:
        raise ValueError("Model selection must not consult frozen-test labels")
    selected_antibiotics = selection.get("antibiotics", {})

    frame = pd.read_csv(args.features)
    required = {"sample_id", "antibiotic", "label", "genetic_group"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    feature_names = sorted(column for column in frame.columns if column.startswith("feature__"))
    if not feature_names:
        raise ValueError("No feature__ columns found")
    marker_feature_names = [
        name for name in feature_names if name.startswith("feature__marker__")
    ]
    if not marker_feature_names:
        raise ValueError("No AMRFinder marker features found")
    organizer_ready = (
        "organizer_split" in frame.columns
        and frame["organizer_split"].astype(str).str.lower().eq("true").all()
    )
    curated_ready = (
        "frozen_split" in frame.columns
        and frame["frozen_split"].astype(str).str.lower().eq("true").all()
        and "split_provenance" in frame.columns
        and frame["split_provenance"].astype(str).str.strip().ne("").all()
    )
    fixed_split_ready = organizer_ready or curated_ready
    if not fixed_split_ready and not args.allow_provisional_split:
        raise ValueError(
            "A frozen grouped split is unavailable. Use --allow-provisional-split "
            "only for non-final development experiments."
        )

    dataset_sha256 = hashlib.sha256(args.features.read_bytes()).hexdigest()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for antibiotic, subset in frame.groupby("antibiotic"):
        antibiotic = str(antibiotic)
        try:
            policy = config.modeling.antibiotics[antibiotic]
        except KeyError as exc:
            raise ValueError(f"Missing modeling policy for {antibiotic}") from exc
        selected = selected_antibiotics.get(antibiotic, {}).get(
            "selected_strategy"
        )
        if selected != policy.strategy:
            raise ValueError(
                f"Configured strategy for {antibiotic} ({policy.strategy}) does "
                f"not match training-only selection evidence ({selected})"
            )
        selected_feature_names = (
            marker_feature_names
            if policy.strategy == "amrfinder_logistic"
            else feature_names
        )
        model_feature_names = [
            name.removeprefix("feature__") for name in selected_feature_names
        ]
        estimator_names = (
            ("logistic_regression",)
            if policy.strategy == "amrfinder_logistic"
            else ("logistic_regression", "hist_gradient_boosting")
        )
        labels = subset["label"].astype(str).str.lower().map(
            {"susceptible": 0, "resistant": 1}
        )
        if labels.isna().any():
            raise ValueError(f"Unknown label found for {antibiotic}")
        bundle = train_model(
            antibiotic,
            subset[selected_feature_names].to_numpy(dtype=float),
            labels.to_numpy(dtype=int),
            subset["genetic_group"].astype(str).to_numpy(),
            model_feature_names,
            alpha=policy.conformal_alpha,
            dataset_sha256=dataset_sha256,
            partitions=(
                subset["split"].astype(str).to_numpy()
                if fixed_split_ready and "split" in subset.columns
                else None
            ),
            estimator_names=estimator_names,
            strategy=policy.strategy,
        )
        output = args.output_dir / artifact_name(antibiotic)
        save_model(bundle, output)
        summary[antibiotic] = {
            "artifact": str(output),
            "strategy": policy.strategy,
            "feature_count": len(selected_feature_names),
            "conformal_alpha": policy.conformal_alpha,
            "metrics": bundle.metrics,
            "dataset_sha256": dataset_sha256,
            "organizer_split": bool(organizer_ready),
            "frozen_split": bool(curated_ready),
            "split_provenance": (
                sorted(subset["split_provenance"].astype(str).unique().tolist())
                if "split_provenance" in subset.columns
                else []
            ),
        }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
