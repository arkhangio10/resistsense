from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import pandas as pd

from resistsense.config import load_config
from resistsense.firewall import DrugEvidence, decide
from resistsense.model_store import artifact_name
from resistsense.modeling import load_model
from resistsense.schemas import AnnotationReport, FastaQcReport
from resistsense.target_annotation import annotate_targets
from resistsense.targets import evaluate_target, load_target_catalog, relevant_markers


TARGET_CACHE_VERSION = "resistsense-target-validation-v1"


def _read_manifest(path: Path) -> dict[str, dict]:
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[str(record["sample_id"])] = record
    return records


def _target_cache_key(catalog_path: Path, reference_manifest: Path) -> str:
    digest = hashlib.sha256()
    digest.update(catalog_path.read_bytes())
    digest.update(reference_manifest.read_bytes())
    return digest.hexdigest()


def _annotate_target_record(
    record: dict,
    cache_dir: Path,
    catalog_path: Path,
    cache_key: str,
    timeout_seconds: int,
) -> dict:
    sample_id = str(record["sample_id"])
    cache_path = cache_dir / f"{sample_id}.json"
    if cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if (
            cached.get("version") == TARGET_CACHE_VERSION
            and cached.get("fasta_sha256") == record["fasta_sha256"]
            and cached.get("target_reference_sha256") == cache_key
        ):
            return cached

    observation = annotate_targets(
        Path(record["fasta_path"]).read_bytes(),
        catalog_path,
        timeout_seconds,
    )
    payload = {
        "version": TARGET_CACHE_VERSION,
        "sample_id": sample_id,
        "fasta_sha256": record["fasta_sha256"],
        "target_reference_sha256": cache_key,
        "available": observation.available,
        "gene_symbols": sorted(observation.gene_symbols or []),
        "error": observation.error,
    }
    temporary = cache_path.with_suffix(".json.partial")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(cache_path)
    return payload


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export frozen grouped-test predictions through the firewall"
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/features/resistsense_features.csv"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/processed/curated/dataset_manifest.jsonl"),
    )
    parser.add_argument(
        "--feature-cache-dir",
        type=Path,
        default=Path("data/processed/features/cache"),
    )
    parser.add_argument(
        "--target-cache-dir",
        type=Path,
        default=Path("data/processed/features/target_cache"),
    )
    parser.add_argument(
        "--model-dir", type=Path, default=Path("artifacts/runtime/models")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/predictions.csv"),
    )
    parser.add_argument("--target-workers", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()
    if args.target_workers < 1:
        raise ValueError("--target-workers must be at least 1")

    config = load_config()
    frame = pd.read_csv(
        args.features,
        dtype={"sample_id": str, "genetic_group": str, "fasta_sha256": str},
    )
    required = {
        "sample_id",
        "antibiotic",
        "label",
        "genetic_group",
        "split",
        "frozen_split",
        "fasta_sha256",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required feature columns: {sorted(missing)}")
    test = frame[frame["split"].astype(str).str.lower().eq("test")].copy()
    if test.empty or not _truthy(test["frozen_split"]).all():
        raise ValueError("A complete frozen test split is required")
    if test.duplicated(["sample_id", "antibiotic"]).any():
        raise ValueError("Test split contains duplicate sample/antibiotic rows")

    manifest = _read_manifest(args.manifest)
    sample_ids = sorted(test["sample_id"].astype(str).unique())
    missing_manifest = sorted(set(sample_ids).difference(manifest))
    if missing_manifest:
        raise ValueError(f"Test samples missing from manifest: {missing_manifest[:5]}")

    catalog_path = Path("configs/drug_targets.yaml")
    reference_manifest = Path("configs/target_references/reference_manifest.json")
    target_cache_key = _target_cache_key(catalog_path, reference_manifest)
    args.target_cache_dir.mkdir(parents=True, exist_ok=True)
    target_observations: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.target_workers) as pool:
        futures = {
            pool.submit(
                _annotate_target_record,
                manifest[sample_id],
                args.target_cache_dir,
                catalog_path,
                target_cache_key,
                config.runtime.target_annotator_timeout_seconds,
            ): sample_id
            for sample_id in sample_ids
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            sample_id = futures[future]
            try:
                target_observations[sample_id] = future.result()
            except Exception as exc:
                target_observations[sample_id] = {
                    "available": False,
                    "gene_symbols": [],
                    "error": str(exc)[:500],
                }
            if args.progress_every > 0 and (
                completed % args.progress_every == 0 or completed == len(futures)
            ):
                available = sum(
                    bool(item.get("available"))
                    for item in target_observations.values()
                )
                print(
                    f"[targets {completed}/{len(futures)}] available={available}",
                    flush=True,
                )

    dataset_sha256 = hashlib.sha256(args.features.read_bytes()).hexdigest()
    targets = load_target_catalog(catalog_path)
    rows = []
    for antibiotic in config.scope.antibiotics:
        subset = test[test["antibiotic"].astype(str).eq(antibiotic)].copy()
        if subset.empty:
            raise ValueError(f"Frozen test split lacks {antibiotic}")
        bundle = load_model(args.model_dir / artifact_name(antibiotic))
        if bundle.dataset_sha256 != dataset_sha256:
            raise ValueError(f"Dataset hash mismatch for {antibiotic}")
        feature_columns = [f"feature__{name}" for name in bundle.feature_names]
        missing_features = sorted(set(feature_columns).difference(subset.columns))
        if missing_features:
            raise ValueError(
                f"Model features missing for {antibiotic}: {missing_features[:5]}"
            )
        predictions = bundle.predict_many(
            subset[feature_columns].to_numpy(dtype=float)
        )

        for (_, row), prediction in zip(subset.iterrows(), predictions, strict=True):
            sample_id = str(row["sample_id"])
            record = manifest[sample_id]
            annotation_payload = json.loads(
                (args.feature_cache_dir / f"{sample_id}.json").read_text(
                    encoding="utf-8"
                )
            )["annotation"]
            annotation = AnnotationReport.model_validate(annotation_payload)
            target_payload = target_observations[sample_id]
            observed_symbols = (
                set(target_payload.get("gene_symbols", []))
                if target_payload.get("available")
                else None
            )
            target_status, target = evaluate_target(
                antibiotic, observed_symbols, targets
            )
            markers = relevant_markers(annotation.markers, target)
            result = decide(
                DrugEvidence(
                    antibiotic=antibiotic,
                    qc=FastaQcReport.model_validate(record["fasta_qc"]),
                    annotation_available=annotation.available,
                    model_available=True,
                    calibrated_probability_resistant=(
                        prediction.probability_resistant
                    ),
                    calibrated=True,
                    conformal_set=prediction.conformal_set,
                    model_probabilities=prediction.model_probabilities,
                    ood_score=prediction.ood_score,
                    target_status=target_status,
                    target_class=target.target_class if target else None,
                    known_markers=markers,
                ),
                config.firewall,
            )
            probabilities = prediction.model_probabilities
            disagreement = max(probabilities.values()) - min(probabilities.values())
            rows.append(
                {
                    "sample_id": sample_id,
                    "antibiotic": antibiotic,
                    "label": str(row["label"]),
                    "genetic_group": str(row["genetic_group"]),
                    "split": "test",
                    "model_strategy": bundle.strategy,
                    "conformal_alpha": bundle.alpha,
                    "probability_resistant": prediction.probability_resistant,
                    "logistic_probability": probabilities.get(
                        "logistic_regression"
                    ),
                    "hist_gradient_boosting_probability": probabilities.get(
                        "hist_gradient_boosting"
                    ),
                    "model_disagreement": disagreement,
                    "conformal_set": "|".join(sorted(prediction.conformal_set)),
                    "ood_score": prediction.ood_score,
                    "target_annotation_available": bool(
                        target_payload.get("available")
                    ),
                    "target_status": target_status.value,
                    "known_marker_count": len(markers),
                    "known_marker_symbols": "|".join(
                        sorted({marker.symbol for marker in markers})
                    ),
                    "final_status": result.final_status.value,
                    "no_call_reasons": "|".join(result.no_call_reasons),
                    "explanation_concordant": (
                        "standard laboratory testing" in result.explanation.lower()
                    ),
                }
            )

    output = pd.DataFrame(rows).sort_values(["sample_id", "antibiotic"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    unavailable = sum(
        not bool(payload.get("available"))
        for payload in target_observations.values()
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(output),
                "samples": output["sample_id"].nunique(),
                "antibiotics": output["antibiotic"].nunique(),
                "target_annotation_unavailable": unavailable,
                "dataset_sha256": dataset_sha256,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
