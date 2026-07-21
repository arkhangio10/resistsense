from __future__ import annotations

import argparse
import json
from pathlib import Path

from resistsense.safety_report import render_markdown, report_from_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an auditable class-aware ResistSense safety report"
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("artifacts/evaluation/predictions.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/class_aware_safety_report.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("docs/class_aware_safety_report.md"),
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    report = report_from_csv(
        args.predictions,
        bootstrap_replicates=args.bootstrap_replicates,
        random_state=args.random_state,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "markdown_output": str(args.markdown_output),
                "antibiotics": len(report["antibiotics"]),
                "research_demo_status": report["research_demo_status"],
                "clinical_release_status": report["clinical_release_status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
