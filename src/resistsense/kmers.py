from __future__ import annotations

import hashlib

from .fasta import parse_fasta


_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _canonical(kmer: str) -> str:
    reverse_complement = kmer.translate(_COMPLEMENT)[::-1]
    return min(kmer, reverse_complement)


def hashed_kmer_mapping(
    content: bytes,
    *,
    k: int,
    buckets: int,
    stride: int,
) -> dict[str, float]:
    """Return stable, strand-invariant hashed k-mer frequencies.

    Ambiguous windows are skipped. Feature hashing fixes the vocabulary before
    the split, which avoids learning a test-only k-mer dictionary.
    """
    if k <= 0 or buckets <= 0 or stride <= 0:
        raise ValueError("k, buckets, and stride must be positive")

    counts = [0] * buckets
    observed = 0
    for record in parse_fasta(content):
        sequence = record.sequence
        for start in range(0, max(0, len(sequence) - k + 1), stride):
            kmer = sequence[start : start + k]
            if len(kmer) != k or set(kmer).difference("ACGT"):
                continue
            canonical = _canonical(kmer)
            digest = hashlib.blake2b(canonical.encode("ascii"), digest_size=8).digest()
            bucket = int.from_bytes(digest, "little") % buckets
            counts[bucket] += 1
            observed += 1

    if observed == 0:
        return {}
    return {
        f"kmer__{index:04d}": count / observed
        for index, count in enumerate(counts)
        if count
    }
