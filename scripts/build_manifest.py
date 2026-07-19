from __future__ import annotations

import argparse
import json
from pathlib import Path

from resistsense.config import load_config
from resistsense.manifest import build_manifest, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
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
        "--output-dir", type=Path, default=Path("data/processed/manifest")
    )
    args = parser.parse_args()
    records, summary = build_manifest(
        args.ast,
        args.metadata,
        args.fasta_dir,
        load_config(),
    )
    write_manifest(records, summary, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
