from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from resistsense.config import load_config
from resistsense.fasta import validate_fasta
from resistsense.manifest import file_sha256


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _download_api(genome_id: str) -> bytes:
    query = (
        f"eq(genome_id,{genome_id})&select(accession,sequence)"
        "&sort(+accession)&limit(10000)"
    )
    url = "https://www.bv-brc.org/api/genome_sequence/?" + quote(
        query,
        safe="(),+&/",
    )
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "ResistSense/0.1"},
    )
    with urlopen(request, timeout=300) as response:
        records = json.loads(response.read().decode("utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("BV-BRC returned no contigs")
    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        sequence = str(record.get("sequence") or "").strip().upper()
        if not sequence:
            continue
        accession = str(record.get("accession") or f"contig_{index}")
        lines.append(f">{accession}")
        lines.extend(sequence[offset : offset + 80] for offset in range(0, len(sequence), 80))
    if not lines:
        raise ValueError("BV-BRC returned contigs without sequence")
    return ("\n".join(lines) + "\n").encode("ascii")


def _download_record(
    record: dict,
    output_dir: Path,
    method: str,
    executable: str | None,
    config,
    skip_existing_validation: bool,
) -> dict:
    genome_id = str(record["sample_id"])
    output = output_dir / f"{genome_id}.fna"
    existed = output.is_file() and output.stat().st_size > 0
    try:
        if existed and skip_existing_validation:
            return {
                "sample_id": genome_id,
                "path": str(output),
                "sha256": None,
                "qc_passed": True,
                "qc_reasons": [],
                "resumed": True,
            }
        if existed:
            content = output.read_bytes()
        elif method == "api":
            content = _download_api(genome_id)
        else:
            assert executable is not None
            result = subprocess.run(
                [executable, genome_id],
                capture_output=True,
                timeout=300,
                check=False,
            )
            if result.returncode != 0 or not result.stdout.startswith(b">"):
                raise RuntimeError(result.stderr.decode(errors="replace")[:300])
            content = result.stdout
        qc = validate_fasta(content, output.name, config.fasta_qc)
        if not existed:
            temporary = output.with_suffix(".fna.partial")
            temporary.write_bytes(content)
            temporary.replace(output)
        return {
            "sample_id": genome_id,
            "path": str(output),
            "sha256": file_sha256(output),
            "qc_passed": qc.passed,
            "qc_reasons": qc.reasons,
            "resumed": existed,
        }
    except Exception as exc:
        return {"sample_id": genome_id, "error": str(exc)[:300]}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download BV-BRC assemblies by genome_id with p3-genome-fasta"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/processed/manifest/dataset_manifest.jsonl"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/fasta"))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--progress-every", type=int, default=50)
    parser.add_argument(
        "--skip-existing-validation",
        action="store_true",
        help="Resume quickly; the final curate_dataset.py pass must revalidate all files",
    )
    parser.add_argument(
        "--method",
        choices=("api", "p3"),
        default="api",
        help="Use the official BV-BRC API or installed p3-genome-fasta CLI",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform downloads; without this flag the command is a dry-run",
    )
    args = parser.parse_args()

    records = [record for record in _records(args.manifest) if not record["fasta_path"]]
    selected = records[: args.limit] if args.limit > 0 else records
    executable = shutil.which("p3-genome-fasta")
    summary = {
        "requested": len(selected),
        "remaining_in_manifest": len(records),
        "execute": args.execute,
        "method": args.method,
        "p3_genome_fasta_available": bool(executable),
        "downloaded": 0,
        "new_downloads": 0,
        "resumed": 0,
        "qc_passed": 0,
        "failed": [],
    }
    if not args.execute:
        print(json.dumps(summary, indent=2))
        return
    if args.method == "p3" and not executable:
        raise RuntimeError(
            "p3-genome-fasta is not installed. Install the official BV-BRC "
            "command-line tools before executing this stage."
        )

    if args.workers < 1:
        raise ValueError("--workers must be at least 1")
    if args.method == "p3" and args.workers != 1:
        raise ValueError("The p3 method must run with --workers 1")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _download_record,
                record,
                args.output_dir,
                args.method,
                executable,
                config,
                args.skip_existing_validation,
            ): record
            for record in selected
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            if "error" in result:
                summary["failed"].append(
                    {"sample_id": result["sample_id"], "reason": result["error"]}
                )
            else:
                summary["downloaded"] += 1
                summary["qc_passed"] += int(result["qc_passed"])
                summary["resumed"] += int(result["resumed"])
                summary["new_downloads"] += int(not result["resumed"])
            if args.progress_every > 0 and (
                completed % args.progress_every == 0 or completed == len(selected)
            ):
                print(
                    json.dumps(
                        {
                            "completed": completed,
                            "requested": len(selected),
                            "downloaded": summary["downloaded"],
                            "qc_passed": summary["qc_passed"],
                            "failed": len(summary["failed"]),
                        }
                    ),
                    flush=True,
                )
    failure_log = args.output_dir / "download_failures.json"
    failure_log.write_text(
        json.dumps(summary["failed"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary["failure_log"] = str(failure_log)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
