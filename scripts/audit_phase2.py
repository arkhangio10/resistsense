"""Audit the BV-BRC AST subset used for ResistSense phase 2.

The script treats a genome/antibiotic pair as the modelling unit. Repeated
laboratory records are collapsed, and pairs with both Resistant and
Susceptible labels are marked as conflicts and excluded from the clean set.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


ANTIBIOTIC_ORDER = [
    "ampicillin",
    "ciprofloxacin",
    "cefotaxime",
    "gentamicin",
    "trimethoprim/sulfamethoxazole",
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nonempty(value: str | None) -> bool:
    return bool((value or "").strip())


def optional_float(value: str | None) -> float | None:
    try:
        return float((value or "").strip())
    except (TypeError, ValueError):
        return None


def numeric_summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        position = round((len(ordered) - 1) * fraction)
        return ordered[position]

    return {
        "count": len(ordered),
        "min": ordered[0],
        "p25": percentile(0.25),
        "median": median(ordered),
        "p75": percentile(0.75),
        "p95": percentile(0.95),
        "max": ordered[-1],
    }


def audit(input_path: Path, genome_metadata_path: Path | None = None) -> dict:
    row_counts = Counter()
    phenotype_rows: dict[str, Counter] = defaultdict(Counter)
    pair_labels: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_row_counts = Counter()
    unique_genomes: dict[str, set[str]] = defaultdict(set)
    completeness: dict[str, Counter] = defaultdict(Counter)
    methods: dict[str, Counter] = defaultdict(Counter)
    standards: dict[str, Counter] = defaultdict(Counter)
    units: dict[str, Counter] = defaultdict(Counter)
    evidence_values = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"genome_id", "antibiotic", "resistant_phenotype"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        for row in reader:
            antibiotic = (row.get("antibiotic") or "").strip()
            phenotype = (row.get("resistant_phenotype") or "").strip()
            genome_id = (row.get("genome_id") or "").strip()
            if antibiotic not in ANTIBIOTIC_ORDER:
                continue
            if phenotype not in {"Resistant", "Susceptible"} or not genome_id:
                continue
            evidence = (row.get("evidence") or "").strip()
            if evidence and evidence != "Laboratory Method":
                raise ValueError(
                    f"Non-laboratory evidence found in lab-only audit: {evidence}"
                )

            key = (genome_id, antibiotic)
            row_counts[antibiotic] += 1
            phenotype_rows[antibiotic][phenotype] += 1
            pair_labels[key].add(phenotype)
            pair_row_counts[key] += 1
            unique_genomes[antibiotic].add(genome_id)
            if evidence:
                evidence_values[evidence] += 1

            for field in (
                "measurement_value",
                "measurement_unit",
                "laboratory_typing_method",
                "testing_standard",
                "testing_standard_year",
                "source",
            ):
                if nonempty(row.get(field)):
                    completeness[antibiotic][field] += 1

            if nonempty(row.get("laboratory_typing_method")):
                methods[antibiotic][row["laboratory_typing_method"].strip()] += 1
            if nonempty(row.get("testing_standard")):
                standards[antibiotic][row["testing_standard"].strip()] += 1
            if nonempty(row.get("measurement_unit")):
                units[antibiotic][row["measurement_unit"].strip()] += 1

    selected_genome_ids = {genome_id for genome_id, _ in pair_labels}
    genome_metadata: dict[str, dict] = {}
    qc_pass_genomes: set[str] = set()
    metadata_summary = None

    if genome_metadata_path is not None:
        quality_counts = Counter()
        status_counts = Counter()
        cluster_counts = Counter()
        numeric_values: dict[str, list[float]] = defaultdict(list)
        assembly_accessions = 0

        with genome_metadata_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                genome_id = (row.get("genome_id") or "").strip()
                if genome_id not in selected_genome_ids:
                    continue
                genome_metadata[genome_id] = row
                quality = (row.get("genome_quality") or "Unknown").strip()
                status = (row.get("genome_status") or "Unknown").strip()
                quality_counts[quality] += 1
                status_counts[status] += 1
                if nonempty(row.get("assembly_accession")):
                    assembly_accessions += 1
                if nonempty(row.get("cgmlst_hc50")):
                    cluster_counts[row["cgmlst_hc50"].strip()] += 1

                parsed = {}
                for field in (
                    "genome_length",
                    "contigs",
                    "contig_n50",
                    "checkm_completeness",
                    "checkm_contamination",
                    "coarse_consistency",
                    "fine_consistency",
                ):
                    parsed[field] = optional_float(row.get(field))
                    if parsed[field] is not None:
                        numeric_values[field].append(parsed[field])

                quality_ok = quality.lower() == "good"
                length_ok = (
                    parsed["genome_length"] is not None
                    and 4_000_000 <= parsed["genome_length"] <= 6_500_000
                )
                contigs_ok = (
                    parsed["contigs"] is not None and parsed["contigs"] <= 500
                )
                completeness_ok = (
                    parsed["checkm_completeness"] is None
                    or parsed["checkm_completeness"] >= 95
                )
                contamination_ok = (
                    parsed["checkm_contamination"] is None
                    or parsed["checkm_contamination"] <= 5
                )
                if (
                    quality_ok
                    and length_ok
                    and contigs_ok
                    and completeness_ok
                    and contamination_ok
                ):
                    qc_pass_genomes.add(genome_id)

        matched = len(genome_metadata)
        largest_cluster = cluster_counts.most_common(1)
        metadata_summary = {
            "input_file": str(genome_metadata_path),
            "input_sha256": file_sha256(genome_metadata_path),
            "selected_unique_genomes": len(selected_genome_ids),
            "metadata_matched_genomes": matched,
            "metadata_match_pct": round(100 * matched / len(selected_genome_ids), 2)
            if selected_genome_ids
            else None,
            "preliminary_qc_pass_genomes": len(qc_pass_genomes),
            "preliminary_qc_pass_pct": round(
                100 * len(qc_pass_genomes) / len(selected_genome_ids), 2
            )
            if selected_genome_ids
            else None,
            "assembly_accession_pct": round(100 * assembly_accessions / matched, 2)
            if matched
            else None,
            "quality_counts": dict(quality_counts),
            "status_counts": dict(status_counts),
            "numeric_summaries": {
                field: numeric_summary(values)
                for field, values in numeric_values.items()
            },
            "cgmlst_hc50": {
                "genomes_with_cluster": sum(cluster_counts.values()),
                "unique_clusters": len(cluster_counts),
                "largest_cluster": largest_cluster[0][0]
                if largest_cluster
                else None,
                "largest_cluster_size": largest_cluster[0][1]
                if largest_cluster
                else 0,
            },
            "preliminary_qc_rule": {
                "genome_quality": "Good",
                "genome_length": "4,000,000-6,500,000 bp",
                "contigs": "<=500",
                "checkm_completeness": ">=95 when available",
                "checkm_contamination": "<=5 when available",
            },
        }

    results = []
    for antibiotic in ANTIBIOTIC_ORDER:
        keys = [key for key in pair_labels if key[1] == antibiotic]
        conflicts = [key for key in keys if len(pair_labels[key]) > 1]
        clean = [key for key in keys if len(pair_labels[key]) == 1]
        clean_counts = Counter(next(iter(pair_labels[key])) for key in clean)
        qc_clean = [key for key in clean if key[0] in qc_pass_genomes]
        qc_clean_counts = Counter(next(iter(pair_labels[key])) for key in qc_clean)
        duplicate_records = sum(max(0, pair_row_counts[key] - 1) for key in keys)
        clean_total = len(clean)

        results.append(
            {
                "antibiotic": antibiotic,
                "raw_records": row_counts[antibiotic],
                "unique_genomes": len(unique_genomes[antibiotic]),
                "unique_genome_antibiotic_pairs": len(keys),
                "duplicate_records": duplicate_records,
                "conflicting_pairs": len(conflicts),
                "eligible_pairs": clean_total,
                "susceptible_pairs": clean_counts["Susceptible"],
                "resistant_pairs": clean_counts["Resistant"],
                "resistant_pct": round(
                    100 * clean_counts["Resistant"] / clean_total, 2
                )
                if clean_total
                else None,
                "measurement_value_pct": round(
                    100 * completeness[antibiotic]["measurement_value"]
                    / row_counts[antibiotic],
                    2,
                )
                if row_counts[antibiotic]
                else None,
                "method_pct": round(
                    100 * completeness[antibiotic]["laboratory_typing_method"]
                    / row_counts[antibiotic],
                    2,
                )
                if row_counts[antibiotic]
                else None,
                "standard_pct": round(
                    100 * completeness[antibiotic]["testing_standard"]
                    / row_counts[antibiotic],
                    2,
                )
                if row_counts[antibiotic]
                else None,
                "top_methods": methods[antibiotic].most_common(10),
                "top_standards": standards[antibiotic].most_common(10),
                "measurement_units": units[antibiotic].most_common(10),
                "preliminary_qc_eligible_pairs": len(qc_clean)
                if genome_metadata_path is not None
                else None,
                "preliminary_qc_susceptible_pairs": qc_clean_counts["Susceptible"]
                if genome_metadata_path is not None
                else None,
                "preliminary_qc_resistant_pairs": qc_clean_counts["Resistant"]
                if genome_metadata_path is not None
                else None,
            }
        )

    conflict_examples = []
    for key, labels in pair_labels.items():
        if len(labels) > 1 and len(conflict_examples) < 25:
            conflict_examples.append(
                {
                    "genome_id": key[0],
                    "antibiotic": key[1],
                    "labels": sorted(labels),
                    "record_count": pair_row_counts[key],
                }
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "BV-BRC public genome_amr API",
        "taxon_id": 562,
        "species": "Escherichia coli",
        "input_file": str(input_path),
        "input_sha256": file_sha256(input_path),
        "evidence_values": dict(evidence_values),
        "total_raw_records": sum(row_counts.values()),
        "unique_genomes_across_selected_antibiotics": len(
            {genome_id for genome_id, _ in pair_labels}
        ),
        "antibiotics": results,
        "genome_metadata": metadata_summary,
        "conflict_examples": conflict_examples,
        "interpretation": {
            "modelling_unit": "unique genome_id + antibiotic",
            "intermediate_policy": "not included in this phase-2 R/S audit",
            "conflict_policy": "exclude pairs containing both Resistant and Susceptible",
            "organizer_dataset_status": "not available; selection is provisional",
            "evidence_policy": "Laboratory Method only",
        },
    }


def write_outputs(summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "phase2_audit.json"
    csv_path = output_dir / "ecoli_antibiotic_matrix.csv"

    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    columns = [
        "antibiotic",
        "raw_records",
        "unique_genomes",
        "unique_genome_antibiotic_pairs",
        "duplicate_records",
        "conflicting_pairs",
        "eligible_pairs",
        "susceptible_pairs",
        "resistant_pairs",
        "resistant_pct",
        "measurement_value_pct",
        "method_pct",
        "standard_pct",
        "preliminary_qc_eligible_pairs",
        "preliminary_qc_susceptible_pairs",
        "preliminary_qc_resistant_pairs",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in summary["antibiotics"]:
            writer.writerow({column: row[column] for column in columns})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/bvbrc/ecoli_phase2_selected_lab.tsv"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/phase2")
    )
    parser.add_argument(
        "--genome-metadata",
        type=Path,
        default=Path("data/raw/bvbrc/ecoli_genome_quality.tsv"),
    )
    args = parser.parse_args()
    summary = audit(args.input, args.genome_metadata)
    write_outputs(summary, args.output_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
