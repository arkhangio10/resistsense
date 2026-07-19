from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TargetObservation:
    available: bool
    gene_symbols: set[str] | None = None
    error: str | None = None


def _resolve_annotator(requested: str) -> str | None:
    resolved = shutil.which(requested)
    if resolved:
        return resolved
    direct = Path(requested)
    if direct.is_file():
        return str(direct.resolve())
    sibling = Path(sys.executable).parent / requested
    candidates = [sibling]
    if sibling.suffix == "":
        candidates.extend(sibling.with_suffix(suffix) for suffix in (".exe", ".cmd"))
    return next((str(path.resolve()) for path in candidates if path.is_file()), None)


def target_annotator_available(executable: str | None = None) -> bool:
    requested = executable or os.getenv(
        "RESISTSENSE_TARGET_ANNOTATOR", "resistsense-target-annotator"
    )
    return bool(requested and _resolve_annotator(requested))


def annotate_targets(
    fasta_content: bytes,
    catalog_path: Path,
    timeout_seconds: int,
    executable: str | None = None,
) -> TargetObservation:
    """Call an independent target annotator through a strict JSON contract.

    The executable must accept ``--fasta``, ``--catalog``, and ``--output`` and
    write ``{"gene_symbols": ["gyrA", ...]}``. AMRFinderPlus output is not
    reused as proof of an intact wild-type target.
    """
    requested = executable or os.getenv(
        "RESISTSENSE_TARGET_ANNOTATOR", "resistsense-target-annotator"
    )
    resolved = _resolve_annotator(requested) if requested else None
    if not resolved:
        return TargetObservation(False, error="Independent target annotator unavailable")

    try:
        with tempfile.TemporaryDirectory(prefix="resistsense-targets-") as temporary:
            root = Path(temporary)
            fasta_path = root / "input.fasta"
            output_path = root / "targets.json"
            fasta_path.write_bytes(fasta_content)
            result = subprocess.run(
                [
                    resolved,
                    "--fasta",
                    str(fasta_path),
                    "--catalog",
                    str(catalog_path.resolve()),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if result.returncode != 0 or not output_path.is_file():
                detail = (result.stderr or result.stdout).strip()
                return TargetObservation(
                    False,
                    error=f"Target annotator failed: {detail[:500]}",
                )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            symbols = payload.get("gene_symbols")
            if not isinstance(symbols, list) or not all(
                isinstance(symbol, str) and symbol.strip() for symbol in symbols
            ):
                return TargetObservation(
                    False,
                    error="Target annotator returned invalid JSON",
                )
            return TargetObservation(True, {symbol.strip() for symbol in symbols})
    except subprocess.TimeoutExpired:
        return TargetObservation(False, error="Target annotator timed out")
    except (OSError, json.JSONDecodeError) as exc:
        return TargetObservation(False, error=f"Target annotator error: {exc}")
