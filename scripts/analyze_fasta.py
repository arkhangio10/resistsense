from __future__ import annotations

import argparse
import json
from pathlib import Path

from resistsense.pipeline import analyze_fasta
from resistsense.reporter import audit_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the fail-closed ResistSense pipeline on one FASTA"
    )
    parser.add_argument("fasta", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    response = analyze_fasta(args.fasta.read_bytes(), args.fasta.name)
    violations = audit_report(response)
    if violations:
        raise RuntimeError(f"Report safety audit failed: {violations}")
    output = args.output or Path("artifacts/runtime/reports") / (
        args.fasta.stem + ".json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(response.model_dump(mode="json"), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "analysis_id": response.analysis_id,
                "qc_passed": response.qc.passed,
                "amrfinderplus": response.annotation.available,
                "markers": len(response.annotation.markers),
                "statuses": {
                    result.antibiotic: result.final_status
                    for result in response.results
                },
                "safety_audit": "passed",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
