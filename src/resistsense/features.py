from __future__ import annotations

import numpy as np

from .config import KmerConfig
from .kmers import hashed_kmer_mapping
from .schemas import FastaQcReport, MarkerEvidence


FEATURE_PIPELINE_VERSION = "resistsense-features-v3"


def feature_mapping(
    markers: list[MarkerEvidence],
    qc: FastaQcReport,
    *,
    fasta_content: bytes | None = None,
    kmer: KmerConfig | None = None,
) -> dict[str, float]:
    features: dict[str, float] = {
        "qc__genome_length_mbp": qc.total_length_bp / 1_000_000,
        "qc__contigs_log1p": float(np.log1p(qc.contigs)),
        "qc__ambiguous_fraction": qc.ambiguous_fraction,
    }
    for marker in markers:
        subtype = (marker.subtype or "AMR").strip().upper()
        if marker.element_type.strip().upper() != "AMR" or subtype not in {
            "AMR",
            "POINT",
        }:
            continue
        symbol = marker.symbol.strip().lower().replace(" ", "_")
        if symbol:
            features[f"marker__{symbol}"] = 1.0
    if fasta_content is not None and kmer is not None and kmer.enabled:
        features.update(
            hashed_kmer_mapping(
                fasta_content,
                k=kmer.k,
                buckets=kmer.buckets,
                stride=kmer.stride,
            )
        )
    return features


def vectorize(mapping: dict[str, float], feature_names: list[str]) -> np.ndarray:
    return np.asarray(
        [[float(mapping.get(feature_name, 0.0)) for feature_name in feature_names]],
        dtype=float,
    )
