from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
from pathlib import Path

from resistsense.amrfinder import annotate_fasta
from resistsense.config import load_config
from resistsense.features import FEATURE_PIPELINE_VERSION, feature_mapping
from resistsense.fasta import validate_fasta


def _read_manifest(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _extract_record(record: dict, cache_dir: Path, config) -> dict:
    cache_path = cache_dir / f"{record['sample_id']}.json"
    cached = None
    if cache_path.is_file():
        candidate = json.loads(cache_path.read_text(encoding="utf-8"))
        if (
            candidate.get("feature_pipeline_version") == FEATURE_PIPELINE_VERSION
            and candidate.get("fasta_sha256") == record["fasta_sha256"]
        ):
            cached = candidate
    if cached is None:
        fasta_path = Path(record["fasta_path"])
        content = fasta_path.read_bytes()
        qc = validate_fasta(content, fasta_path.name, config.fasta_qc)
        if not qc.passed:
            raise RuntimeError(
                f"FASTA QC failed for {record['sample_id']}: {qc.reasons}"
            )
        annotation = annotate_fasta(
            content,
            config.scope.species.amrfinderplus_organism,
            config.runtime.amrfinder_timeout_seconds,
        )
        if not annotation.available:
            raise RuntimeError(
                f"AMRFinderPlus failed for {record['sample_id']}: {annotation.error}"
            )
        cached = {
            "feature_pipeline_version": FEATURE_PIPELINE_VERSION,
            "sample_id": record["sample_id"],
            "fasta_sha256": record["fasta_sha256"],
            "annotation": annotation.model_dump(mode="json"),
            "features": feature_mapping(
                annotation.markers,
                qc,
                fasta_content=content,
                kmer=config.features.kmer,
            ),
        }
        temporary = cache_path.with_suffix(".json.partial")
        temporary.write_text(
            json.dumps(cached, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temporary.replace(cache_path)

    cached.update(
        {
            "genetic_group": record["genetic_group"],
            "split": record["split"],
            "organizer_split": record.get("organizer_split", False),
            "frozen_split": record.get("frozen_split", False),
            "split_provenance": record.get("split_provenance", "provisional"),
            "labels": record["labels"],
            "fasta_sha256": record["fasta_sha256"],
        }
    )
    return cached


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract cached AMRFinderPlus, QC, and hashed k-mer features"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/processed/manifest/dataset_manifest.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/features/resistsense_features.csv"),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/processed/features/cache"),
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()

    config = load_config()
    records = [record for record in _read_manifest(args.manifest) if record["fasta_path"]]
    if args.limit > 0:
        records = records[: args.limit]
    if not records:
        raise ValueError("Manifest contains no FASTA paths")
    if args.workers < 1:
        raise ValueError("--workers must be at least 1")

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    cached_rows: list[dict] = []
    feature_names: set[str] = set()
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_extract_record, record, args.cache_dir, config): record
            for record in records
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            record = futures[future]
            try:
                cached = future.result()
            except Exception as exc:
                failures.append(
                    {"sample_id": record["sample_id"], "reason": str(exc)[:500]}
                )
            else:
                cached_rows.append(cached)
                feature_names.update(cached["features"])
            if args.progress_every > 0 and (
                completed % args.progress_every == 0 or completed == len(records)
            ):
                print(
                    f"[{completed}/{len(records)}] cached={len(cached_rows)} "
                    f"failed={len(failures)}",
                    flush=True,
                )

    failure_path = args.cache_dir / "feature_failures.json"
    failure_path.write_text(
        json.dumps(failures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if failures:
        raise RuntimeError(
            f"Feature extraction failed for {len(failures)} genomes; see {failure_path}"
        )
    cached_rows.sort(key=lambda row: str(row["sample_id"]))

    columns = sorted(feature_names)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_id",
                "antibiotic",
                "label",
                "genetic_group",
                "split",
                "organizer_split",
                "frozen_split",
                "split_provenance",
                "fasta_sha256",
                *[f"feature__{name}" for name in columns],
            ],
        )
        writer.writeheader()
        for cached in cached_rows:
            base = {
                "sample_id": cached["sample_id"],
                "genetic_group": cached["genetic_group"],
                "split": cached["split"],
                "organizer_split": cached["organizer_split"],
                "frozen_split": cached["frozen_split"],
                "split_provenance": cached["split_provenance"],
                "fasta_sha256": cached["fasta_sha256"],
                **{
                    f"feature__{name}": cached["features"].get(name, 0.0)
                    for name in columns
                },
            }
            for antibiotic, label in sorted(cached["labels"].items()):
                writer.writerow({**base, "antibiotic": antibiotic, "label": label})

    print(
        json.dumps(
            {
                "output": str(args.output),
                "samples": len(cached_rows),
                "features": len(columns),
                "rows": sum(len(row["labels"]) for row in cached_rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
