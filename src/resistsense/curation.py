from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .config import ResistSenseConfig
from .fasta import validate_fasta
from .manifest import file_sha256


CURATION_VERSION = "resistsense-ecoli-lab-cgmlst-v1"
SPLIT_PROPORTIONS = {
    "train": 0.60,
    "probability_calibration": 0.15,
    "conformal_calibration": 0.10,
    "test": 0.15,
}


def _number(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def _metadata_qc_reasons(row: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    length = _number(row.get("genome_length"))
    contigs = _number(row.get("contigs"))
    completeness = _number(row.get("checkm_completeness"))
    contamination = _number(row.get("checkm_contamination"))

    if (row.get("genome_quality") or "").strip() != "Good":
        reasons.append("genome_quality_not_good")
    if length is None or not 4_000_000 <= length <= 6_500_000:
        reasons.append("genome_length_out_of_range")
    if contigs is None or contigs > 500:
        reasons.append("too_many_contigs")
    if completeness is not None and completeness < 95:
        reasons.append("checkm_completeness_below_95")
    if contamination is not None and contamination > 5:
        reasons.append("checkm_contamination_above_5")
    if not (row.get("cgmlst_hc50") or "").strip():
        reasons.append("missing_cgmlst_hc50")
    return reasons


def _stable_tie_breaker(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def assign_group_partitions(records: list[dict]) -> dict[str, str]:
    """Assign complete cgMLST groups to deterministic multilabel partitions."""

    if not records:
        raise ValueError("Cannot partition an empty cohort")
    antibiotics = sorted(
        {antibiotic for record in records for antibiotic in record["labels"]}
    )
    dimensions = ["samples"] + [
        f"{antibiotic}:{label}"
        for antibiotic in antibiotics
        for label in ("resistant", "susceptible")
    ]
    by_group: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_group[str(record["genetic_group"])].append(record)

    vectors: dict[str, dict[str, int]] = {}
    totals = {dimension: 0 for dimension in dimensions}
    for group, members in by_group.items():
        vector = {dimension: 0 for dimension in dimensions}
        vector["samples"] = len(members)
        for member in members:
            for antibiotic, label in member["labels"].items():
                vector[f"{antibiotic}:{label}"] += 1
        vectors[group] = vector
        for dimension, value in vector.items():
            totals[dimension] += value

    targets = {
        split: {
            dimension: totals[dimension] * proportion
            for dimension in dimensions
        }
        for split, proportion in SPLIT_PROPORTIONS.items()
    }
    assigned = {
        split: {dimension: 0 for dimension in dimensions}
        for split in SPLIT_PROPORTIONS
    }

    def group_priority(group: str) -> tuple[float, int, int]:
        vector = vectors[group]
        rarity = max(
            vector[dimension] / max(totals[dimension], 1)
            for dimension in dimensions
        )
        return rarity, vector["samples"], _stable_tie_breaker(group)

    group_to_split: dict[str, str] = {}
    for group in sorted(by_group, key=group_priority, reverse=True):
        vector = vectors[group]
        candidates: list[tuple[float, int, str]] = []
        for split in SPLIT_PROPORTIONS:
            cost = 0.0
            for candidate_split in SPLIT_PROPORTIONS:
                for dimension in dimensions:
                    value = assigned[candidate_split][dimension]
                    if candidate_split == split:
                        value += vector[dimension]
                    target = targets[candidate_split][dimension]
                    cost += ((value - target) ** 2) / max(target, 1.0)
                    if value > target:
                        cost += 2.0 * ((value - target) ** 2) / max(target, 1.0)
            candidates.append(
                (cost, _stable_tie_breaker(f"{CURATION_VERSION}:{group}:{split}"), split)
            )
        _, _, selected = min(candidates)
        group_to_split[group] = selected
        for dimension, value in vector.items():
            assigned[selected][dimension] += value

    for split in SPLIT_PROPORTIONS:
        split_records = [
            record
            for record in records
            if group_to_split[str(record["genetic_group"])] == split
        ]
        if not split_records:
            raise ValueError(f"Partition {split} is empty")
        for antibiotic in antibiotics:
            observed = {record["labels"][antibiotic] for record in split_records}
            if observed != {"resistant", "susceptible"}:
                raise ValueError(
                    f"Partition {split} lacks both classes for {antibiotic}"
                )
    return group_to_split


def build_curated_cohort(
    ast_path: Path,
    metadata_path: Path,
    fasta_dir: Path,
    config: ResistSenseConfig,
) -> tuple[list[dict], list[dict], dict]:
    required_antibiotics = tuple(config.scope.antibiotics)
    labels: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    duplicate_rows = 0
    seen_rows: set[tuple[str, str, str]] = set()
    with ast_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if (row.get("evidence") or "").strip() != "Laboratory Method":
                continue
            genome_id = (row.get("genome_id") or "").strip()
            antibiotic = (row.get("antibiotic") or "").strip().lower()
            label = (row.get("resistant_phenotype") or "").strip().lower()
            if not genome_id or antibiotic not in required_antibiotics:
                continue
            if label not in {"resistant", "susceptible"}:
                continue
            key = (genome_id, antibiotic, label)
            duplicate_rows += int(key in seen_rows)
            seen_rows.add(key)
            labels[genome_id][antibiotic].add(label)

    metadata: dict[str, dict[str, str]] = {}
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            genome_id = (row.get("genome_id") or "").strip()
            if genome_id in labels and genome_id not in metadata:
                metadata[genome_id] = row

    fasta_by_id = {
        path.stem: path
        for path in fasta_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".fa", ".fna", ".fasta"}
    } if fasta_dir.is_dir() else {}

    records: list[dict] = []
    exclusions: list[dict] = []
    conflicting_pairs = 0
    for genome_id in sorted(labels):
        reasons: list[str] = []
        clean_labels: dict[str, str] = {}
        for antibiotic in required_antibiotics:
            observed = labels[genome_id].get(antibiotic, set())
            if len(observed) > 1:
                conflicting_pairs += 1
                reasons.append(f"conflicting_label:{antibiotic}")
            elif len(observed) == 1:
                clean_labels[antibiotic] = next(iter(observed))
            else:
                reasons.append(f"missing_label:{antibiotic}")
        row = metadata.get(genome_id)
        if row is None:
            reasons.append("missing_genome_metadata")
        else:
            reasons.extend(_metadata_qc_reasons(row))
        if reasons:
            exclusions.append(
                {"sample_id": genome_id, "reasons": sorted(set(reasons))}
            )
            continue

        assert row is not None
        fasta_path = fasta_by_id.get(genome_id)
        fasta_qc = None
        if fasta_path is not None:
            fasta_qc = validate_fasta(
                fasta_path.read_bytes(), fasta_path.name, config.fasta_qc
            ).model_dump(mode="json")
            if not fasta_qc["passed"]:
                exclusions.append(
                    {
                        "sample_id": genome_id,
                        "reasons": [
                            f"fasta_qc:{reason}" for reason in fasta_qc["reasons"]
                        ],
                    }
                )
                continue
        records.append(
            {
                "sample_id": genome_id,
                "species": config.scope.species.scientific_name,
                "taxon_id": config.scope.species.taxon_id,
                "genetic_group": str(row["cgmlst_hc50"]).strip(),
                "split": None,
                "split_provenance": CURATION_VERSION,
                "frozen_split": True,
                "organizer_split": False,
                "labels": clean_labels,
                "fasta_path": str(fasta_path) if fasta_path else None,
                "fasta_sha256": fasta_qc["sha256"] if fasta_qc else None,
                "fasta_qc": fasta_qc,
                "genome_quality": row.get("genome_quality"),
                "genome_length": row.get("genome_length"),
                "contigs": row.get("contigs"),
                "assembly_accession": row.get("assembly_accession"),
                "collection_year": row.get("collection_year"),
                "isolation_country": row.get("isolation_country"),
            }
        )

    group_to_split = assign_group_partitions(records)
    for record in records:
        record["split"] = group_to_split[str(record["genetic_group"])]

    balance: list[dict] = []
    for split in SPLIT_PROPORTIONS:
        for antibiotic in required_antibiotics:
            split_labels = [
                record["labels"][antibiotic]
                for record in records
                if record["split"] == split
            ]
            balance.append(
                {
                    "split": split,
                    "antibiotic": antibiotic,
                    "samples": len(split_labels),
                    "resistant": split_labels.count("resistant"),
                    "susceptible": split_labels.count("susceptible"),
                }
            )

    samples_with_fasta = sum(record["fasta_path"] is not None for record in records)
    samples_passing_fasta_qc = sum(
        bool(record["fasta_qc"] and record["fasta_qc"]["passed"])
        for record in records
    )
    acquisition_complete = (
        samples_with_fasta == len(records)
        and samples_passing_fasta_qc == len(records)
    )
    summary = {
        "status": (
            "self_curated_frozen_cohort"
            if acquisition_complete
            else "self_curated_candidate_cohort"
        ),
        "curation_version": CURATION_VERSION,
        "source": "BV-BRC genome_amr; evidence=Laboratory Method",
        "species": config.scope.species.scientific_name,
        "antibiotics": list(required_antibiotics),
        "samples": len(records),
        "genetic_groups": len({record["genetic_group"] for record in records}),
        "excluded_samples": len(exclusions),
        "conflicting_pairs_excluded": conflicting_pairs,
        "duplicate_same_label_rows_collapsed": duplicate_rows,
        "samples_with_fasta": samples_with_fasta,
        "samples_missing_fasta": len(records) - samples_with_fasta,
        "samples_passing_fasta_qc": samples_passing_fasta_qc,
        "acquisition_complete": acquisition_complete,
        "split_counts": {
            split: sum(record["split"] == split for record in records)
            for split in SPLIT_PROPORTIONS
        },
        "ast_sha256": file_sha256(ast_path),
        "metadata_sha256": file_sha256(metadata_path),
        "balance": balance,
    }
    return records, exclusions, summary


def write_curated_cohort(
    records: list[dict], exclusions: list[dict], summary: dict, output_dir: Path
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "dataset_manifest.jsonl"
    manifest_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    summary = {**summary, "manifest_sha256": file_sha256(manifest_path)}
    (output_dir / "manifest_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    with (output_dir / "cohort_labels.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_id",
                "genetic_group",
                "split",
                "antibiotic",
                "label",
            ],
        )
        writer.writeheader()
        for record in records:
            for antibiotic, label in record["labels"].items():
                writer.writerow(
                    {
                        "sample_id": record["sample_id"],
                        "genetic_group": record["genetic_group"],
                        "split": record["split"],
                        "antibiotic": antibiotic,
                        "label": label,
                    }
                )

    with (output_dir / "exclusions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "reasons"])
        writer.writeheader()
        for exclusion in exclusions:
            writer.writerow(
                {
                    "sample_id": exclusion["sample_id"],
                    "reasons": ";".join(exclusion["reasons"]),
                }
            )

    with (output_dir / "antibiotic_balance.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["split", "antibiotic", "samples", "resistant", "susceptible"],
        )
        writer.writeheader()
        writer.writerows(summary["balance"])

    data_dictionary = {
        "sample_id": "BV-BRC genome identifier",
        "genetic_group": "BV-BRC cgMLST HC50 cluster; never crosses partitions",
        "split": "Frozen train, probability-calibration, conformal-calibration, or test partition",
        "antibiotic": "One of the five declared ResistSense endpoints",
        "label": "Laboratory-measured resistant or susceptible phenotype",
        "fasta_sha256": "SHA-256 checksum of the downloaded assembled genome",
        "split_provenance": CURATION_VERSION,
    }
    (output_dir / "data_dictionary.json").write_text(
        json.dumps(data_dictionary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary
