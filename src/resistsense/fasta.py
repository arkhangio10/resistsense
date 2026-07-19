from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .config import FastaQcConfig
from .schemas import FastaQcReport


@dataclass(frozen=True)
class FastaRecord:
    header: str
    sequence: str


def parse_fasta(content: bytes) -> list[FastaRecord]:
    if content.startswith(b"\x1f\x8b"):
        raise ValueError("Compressed FASTA is not accepted; upload plain-text FASTA")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("FASTA must be UTF-8 plain text") from exc

    records: list[FastaRecord] = []
    header: str | None = None
    chunks: list[str] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith(">"):
            if header is not None:
                records.append(FastaRecord(header, "".join(chunks).upper()))
            header = line[1:].strip() or f"contig_{len(records) + 1}"
            chunks = []
            continue
        if header is None:
            raise ValueError(f"Sequence found before FASTA header on line {line_number}")
        chunks.append("".join(line.split()))

    if header is not None:
        records.append(FastaRecord(header, "".join(chunks).upper()))
    if not records:
        raise ValueError("No FASTA records found")
    if any(not record.sequence for record in records):
        raise ValueError("Every FASTA record must contain a sequence")
    return records


def validate_fasta(
    content: bytes,
    filename: str,
    policy: FastaQcConfig,
) -> FastaQcReport:
    digest = hashlib.sha256(content).hexdigest()
    try:
        records = parse_fasta(content)
    except ValueError as exc:
        return FastaQcReport(
            passed=False,
            sha256=digest,
            filename=Path(filename).name,
            total_length_bp=0,
            contigs=0,
            ambiguous_bases=0,
            ambiguous_fraction=0,
            reasons=[str(exc)],
        )

    allowed = set(policy.allowed_bases.upper())
    canonical = set("ACGT")
    observed: set[str] = set()
    ambiguous = 0
    total = 0
    for record in records:
        observed.update(record.sequence)
        length = len(record.sequence)
        canonical_count = sum(record.sequence.count(base) for base in canonical)
        ambiguous += length - canonical_count
        total += length
    invalid = sorted(observed.difference(allowed))
    ambiguous_fraction = ambiguous / total if total else 1.0
    reasons: list[str] = []

    if invalid:
        reasons.append(f"invalid_sequence_characters:{''.join(invalid)}")
    if total < policy.min_genome_length_bp:
        reasons.append("genome_length_below_supported_range")
    if total > policy.max_genome_length_bp:
        reasons.append("genome_length_above_supported_range")
    if len(records) > policy.max_contigs:
        reasons.append("too_many_contigs")
    if ambiguous_fraction > policy.max_ambiguous_fraction:
        reasons.append("too_many_ambiguous_bases")

    return FastaQcReport(
        passed=not reasons,
        sha256=digest,
        filename=Path(filename).name,
        total_length_bp=total,
        contigs=len(records),
        ambiguous_bases=ambiguous,
        ambiguous_fraction=round(ambiguous_fraction, 8),
        invalid_characters=invalid,
        reasons=reasons,
    )
