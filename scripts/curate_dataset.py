from __future__ import annotations

import argparse
import json
from pathlib import Path

from resistsense.config import load_config
from resistsense.curation import build_curated_cohort, write_curated_cohort


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the frozen, self-curated ResistSense BV-BRC cohort"
    )
    parser.add_argument(
        "--ast",
        type=Path,
        default=Path("data/raw/bvbrc/ecoli_phase2_selected_lab.tsv"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("data/raw/bvbrc/ecoli_genome_quality.tsv"),
    )
    parser.add_argument("--fasta-dir", type=Path, default=Path("data/raw/fasta"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/curated")
    )
    parser.add_argument(
        "--public-summary",
        type=Path,
        default=Path("artifacts/phase2/curated_cohort_summary.json"),
    )
    args = parser.parse_args()

    records, exclusions, summary = build_curated_cohort(
        args.ast, args.metadata, args.fasta_dir, load_config()
    )
    frozen = write_curated_cohort(records, exclusions, summary, args.output_dir)
    public = {
        key: value
        for key, value in frozen.items()
        if key
        not in {
            "ast_sha256",
            "metadata_sha256",
        }
    }
    args.public_summary.parent.mkdir(parents=True, exist_ok=True)
    args.public_summary.write_text(
        json.dumps(public, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(frozen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
