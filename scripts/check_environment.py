from __future__ import annotations

import json
import shutil
from pathlib import Path

from resistsense.amrfinder import amrfinder_runtime_available
from resistsense.config import load_config
from resistsense.model_store import artifact_name
from resistsense.target_annotation import target_annotator_available


def main() -> None:
    config = load_config()
    payload = {
        "config": True,
        "amrfinderplus": amrfinder_runtime_available(),
        "bvbrc_api_downloader": True,
        "p3_genome_fasta": shutil.which("p3-genome-fasta") is not None,
        "independent_target_annotator": target_annotator_available(),
        "raw_ast": Path("data/raw/bvbrc/ecoli_phase2_selected_lab.tsv").is_file(),
        "genome_metadata": Path("data/raw/bvbrc/ecoli_genome_quality.tsv").is_file(),
        "fasta_files": sum(
            1
            for path in Path("data/raw/fasta").glob("*")
            if path.suffix.lower() in {".fa", ".fna", ".fasta"}
        ),
        "models": {
            antibiotic: (config.runtime.model_dir / artifact_name(antibiotic)).is_file()
            for antibiotic in config.scope.antibiotics
        },
    }
    payload["full_runtime_ready"] = (
        payload["amrfinderplus"]
        and payload["independent_target_annotator"]
        and all(payload["models"].values())
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
