from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from .schemas import AnnotationReport, MarkerEvidence


PINNED_DOCKER_IMAGE = (
    "ncbi/amr@sha256:5dbf95e3c571c4964c1eaf2f8fd50884ac2a996c4b1a6e4af5a09e381b71d01f"
)


def _value(row: dict[str, str], *names: str) -> str | None:
    lowered = {key.lower().strip(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value and value.strip():
            return value.strip()
    return None


def _percent(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = float(value.rstrip("%"))
    except ValueError:
        return None
    return round(parsed / 100 if parsed > 1 else parsed, 6)


def parse_amrfinder_tsv(path: Path) -> list[MarkerEvidence]:
    markers: list[MarkerEvidence] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            symbol = _value(row, "Gene symbol", "Gene", "Element symbol")
            if not symbol:
                continue
            markers.append(
                MarkerEvidence(
                    symbol=symbol,
                    element_type=_value(row, "Element type") or "AMR",
                    subtype=_value(row, "Element subtype", "Subtype"),
                    identity=_percent(_value(row, "% Identity", "Identity")),
                    coverage=_percent(
                        _value(row, "% Coverage of reference sequence", "Coverage")
                    ),
                    resistance_class=_value(row, "Class"),
                    subclass=_value(row, "Subclass"),
                )
            )
    return markers


def _version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else None


@lru_cache(maxsize=1)
def _docker_ready() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        result = subprocess.run(
            [docker, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def amrfinder_runtime_available(executable: str | None = None) -> bool:
    requested = executable or os.getenv("AMRFINDER_BIN", "amrfinder")
    return shutil.which(requested) is not None or _docker_ready()


def annotate_fasta(
    fasta_content: bytes,
    organism: str,
    timeout_seconds: int,
    executable: str | None = None,
) -> AnnotationReport:
    requested = executable or os.getenv("AMRFINDER_BIN", "amrfinder")
    resolved = shutil.which(requested)
    docker = shutil.which("docker") if _docker_ready() else None
    docker_image = os.getenv("AMRFINDER_DOCKER_IMAGE", PINNED_DOCKER_IMAGE)
    if not resolved and not docker:
        return AnnotationReport(
            available=False,
            error="AMRFinderPlus executable or Docker runtime is not available",
        )

    try:
        with tempfile.TemporaryDirectory(prefix="resistsense-amrfinder-") as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.fasta"
            output_path = tmp_path / "amrfinder.tsv"
            input_path.write_bytes(fasta_content)
            if resolved:
                command = [
                    resolved,
                    "-n",
                    str(input_path),
                    "-O",
                    organism,
                    "--plus",
                    "-o",
                    str(output_path),
                ]
                tool_version = _version(resolved)
            else:
                assert docker is not None
                command = [
                    docker,
                    "run",
                    "--rm",
                    "-v",
                    f"{tmp_path.resolve()}:/data",
                    docker_image,
                    "amrfinder",
                    "-n",
                    "/data/input.fasta",
                    "-O",
                    organism,
                    "--plus",
                    "-o",
                    "/data/amrfinder.tsv",
                ]
                tool_version = docker_image
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                return AnnotationReport(
                    available=False,
                    tool_version=tool_version,
                    error=f"AMRFinderPlus failed: {detail[:500]}",
                )
            markers = parse_amrfinder_tsv(output_path) if output_path.exists() else []
            return AnnotationReport(
                available=True,
                tool_version=tool_version,
                markers=markers,
            )
    except subprocess.TimeoutExpired:
        return AnnotationReport(
            available=False,
            tool_version=_version(resolved) if resolved else docker_image,
            error="AMRFinderPlus timed out",
        )
    except OSError as exc:
        return AnnotationReport(
            available=False,
            tool_version=_version(resolved) if resolved else docker_image,
            error=f"AMRFinderPlus execution error: {exc}",
        )
