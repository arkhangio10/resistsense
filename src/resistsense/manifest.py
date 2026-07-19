from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from .fasta import validate_fasta
from .config import ResistSenseConfig


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def provisional_group_split(group: str, seed: str = "resistsense-v1") -> str:
    """Deterministic fallback only; organizer-provided splits take precedence."""
    value = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) % 100
    if value < 70:
        return "train"
    if value < 85:
        return "calibration"
    return "test"


def _fasta_index(fasta_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not fasta_dir.is_dir():
        return index
    for path in fasta_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".fa", ".fna", ".fasta"}:
            index.setdefault(path.stem, path)
    return index


def build_manifest(
    ast_path: Path,
    metadata_path: Path,
    fasta_dir: Path,
    config: ResistSenseConfig,
) -> tuple[list[dict], dict]:
    labels: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    with ast_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if (row.get("evidence") or "").strip() != "Laboratory Method":
                continue
            genome_id = (row.get("genome_id") or "").strip()
            antibiotic = (row.get("antibiotic") or "").strip().lower()
            label = (row.get("resistant_phenotype") or "").strip().lower()
            if (
                genome_id
                and antibiotic in config.scope.antibiotics
                and label in {"resistant", "susceptible"}
            ):
                labels[genome_id][antibiotic].add(label)

    metadata: dict[str, dict] = {}
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            genome_id = (row.get("genome_id") or "").strip()
            if genome_id in labels:
                metadata[genome_id] = row

    fasta_by_id = _fasta_index(fasta_dir)
    records = []
    conflict_pairs = 0
    for genome_id in sorted(labels):
        clean_labels = {}
        for antibiotic, observed in labels[genome_id].items():
            if len(observed) == 1:
                clean_labels[antibiotic] = next(iter(observed))
            else:
                conflict_pairs += 1
        row = metadata.get(genome_id, {})
        group = (row.get("cgmlst_hc50") or "").strip() or f"unclustered:{genome_id}"
        fasta_path = fasta_by_id.get(genome_id)
        fasta_qc = None
        if fasta_path:
            fasta_qc = validate_fasta(
                fasta_path.read_bytes(), fasta_path.name, config.fasta_qc
            ).model_dump(mode="json")
        records.append(
            {
                "sample_id": genome_id,
                "species": config.scope.species.scientific_name,
                "taxon_id": config.scope.species.taxon_id,
                "genetic_group": group,
                "split": provisional_group_split(group),
                "labels": clean_labels,
                "fasta_path": str(fasta_path) if fasta_path else None,
                "fasta_sha256": file_sha256(fasta_path) if fasta_path else None,
                "fasta_qc": fasta_qc,
                "genome_quality": row.get("genome_quality"),
                "genome_length": row.get("genome_length"),
                "contigs": row.get("contigs"),
                "organizer_split": False,
            }
        )

    summary = {
        "status": "provisional_until_organizer_dataset_and_split",
        "samples": len(records),
        "samples_with_fasta": sum(record["fasta_path"] is not None for record in records),
        "samples_passing_fasta_qc": sum(
            bool(record["fasta_qc"] and record["fasta_qc"]["passed"])
            for record in records
        ),
        "metadata_matched": sum(record["sample_id"] in metadata for record in records),
        "conflicting_pairs_excluded": conflict_pairs,
        "split_counts": {
            split: sum(record["split"] == split for record in records)
            for split in ("train", "calibration", "test")
        },
        "ast_sha256": file_sha256(ast_path),
        "metadata_sha256": file_sha256(metadata_path),
    }
    return records, summary


def write_manifest(records: list[dict], summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl = output_dir / "dataset_manifest.jsonl"
    jsonl.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    (output_dir / "manifest_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
