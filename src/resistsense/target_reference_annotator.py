from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from .amrfinder import PINNED_DOCKER_IMAGE


def _run_blast(root: Path, image: str, timeout: int) -> None:
    blastn = shutil.which("blastn")
    tblastn = shutil.which("tblastn")
    if blastn and tblastn:
        commands = (
            (
                [
                    tblastn,
                    "-query",
                    str(root / "targets.faa"),
                    "-subject",
                    str(root / "input.fasta"),
                    "-evalue",
                    "1e-20",
                    "-seg",
                    "yes",
                    "-outfmt",
                    "6 qseqid pident length qlen evalue bitscore",
                ],
                root / "protein_hits.tsv",
            ),
            (
                [
                    blastn,
                    "-query",
                    str(root / "rrs.fna"),
                    "-subject",
                    str(root / "input.fasta"),
                    "-evalue",
                    "1e-30",
                    "-dust",
                    "yes",
                    "-outfmt",
                    "6 qseqid pident length qlen evalue bitscore",
                ],
                root / "rrs_hits.tsv",
            ),
        )
        for command, output in commands:
            with output.open("w", encoding="utf-8") as handle:
                result = subprocess.run(
                    command,
                    stdout=handle,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Independent target BLAST failed: {result.stderr.strip()[:500]}"
                )
        return

    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError(
            "Local blastn/tblastn executables or Docker are required for the "
            "independent target annotator"
        )
    command = (
        "tblastn -query /data/targets.faa -subject /data/input.fasta "
        "-evalue 1e-20 -seg yes -outfmt '6 qseqid pident length qlen evalue bitscore' "
        "> /data/protein_hits.tsv && "
        "blastn -query /data/rrs.fna -subject /data/input.fasta "
        "-evalue 1e-30 -dust yes -outfmt '6 qseqid pident length qlen evalue bitscore' "
        "> /data/rrs_hits.tsv"
    )
    result = subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{root.resolve()}:/data",
            image,
            "sh",
            "-lc",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Independent target BLAST failed: {detail[:500]}")


def _accepted_hits(
    path: Path, *, minimum_identity: float, minimum_coverage: float
) -> tuple[set[str], list[dict]]:
    symbols: set[str] = set()
    evidence: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) != 6:
                continue
            query, identity, length, query_length, evalue, bitscore = row
            coverage = min(1.0, float(length) / float(query_length))
            accepted = float(identity) >= minimum_identity and coverage >= minimum_coverage
            symbol = query.split("|", 1)[0]
            evidence.append(
                {
                    "symbol": symbol,
                    "identity": round(float(identity) / 100, 6),
                    "coverage": round(coverage, 6),
                    "evalue": float(evalue),
                    "bitscore": float(bitscore),
                    "accepted": accepted,
                }
            )
            if accepted:
                symbols.add(symbol)
    return symbols, evidence


def annotate(
    fasta: Path,
    catalog: Path,
    references: Path,
    image: str,
    timeout: int,
) -> dict:
    raw_catalog = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    required = {
        symbol
        for drug in raw_catalog["antibiotics"].values()
        for group in drug["required_groups"]
        for symbol in group
    }
    protein_reference = references / "ecoli_k12_targets.faa"
    rrs_reference = references / "ecoli_k12_rrs.fna"
    reference_manifest = references / "reference_manifest.json"
    for path in (protein_reference, rrs_reference, reference_manifest):
        if not path.is_file():
            raise FileNotFoundError(f"Missing frozen target reference: {path}")

    with tempfile.TemporaryDirectory(prefix="resistsense-target-blast-") as temporary:
        root = Path(temporary)
        shutil.copyfile(fasta, root / "input.fasta")
        shutil.copyfile(protein_reference, root / "targets.faa")
        shutil.copyfile(rrs_reference, root / "rrs.fna")
        _run_blast(root, image, timeout)
        protein_symbols, protein_evidence = _accepted_hits(
            root / "protein_hits.tsv",
            minimum_identity=80,
            minimum_coverage=0.80,
        )
        rrs_symbols, rrs_evidence = _accepted_hits(
            root / "rrs_hits.tsv",
            minimum_identity=95,
            minimum_coverage=0.80,
        )

    symbols = sorted((protein_symbols | rrs_symbols).intersection(required))
    manifest = json.loads(reference_manifest.read_text(encoding="utf-8"))
    return {
        "gene_symbols": symbols,
        "evidence": protein_evidence + rrs_evidence,
        "method": "independent_reference_alignment",
        "reference_assembly": manifest["assembly"],
        "reference_checksums": manifest["outputs"],
        "docker_image": image,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Independently verify ResistSense molecular targets"
    )
    parser.add_argument("--fasta", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--references", type=Path, default=Path("configs/target_references")
    )
    parser.add_argument("--docker-image", default=PINNED_DOCKER_IMAGE)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    payload = annotate(
        args.fasta,
        args.catalog,
        args.references,
        args.docker_image,
        args.timeout,
    )
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
