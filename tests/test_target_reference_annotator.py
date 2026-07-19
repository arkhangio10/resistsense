from __future__ import annotations

from pathlib import Path

from resistsense.target_reference_annotator import _accepted_hits


def test_target_hit_requires_identity_and_coverage(tmp_path: Path) -> None:
    hits = tmp_path / "hits.tsv"
    hits.write_text(
        "gyrA|reference\t98.5\t870\t875\t0\t1000\n"
        "parC|reference\t99.0\t300\t750\t1e-50\t300\n"
        "folA|reference\t55.0\t159\t159\t1e-40\t250\n",
        encoding="utf-8",
    )

    symbols, evidence = _accepted_hits(
        hits, minimum_identity=80, minimum_coverage=0.80
    )

    assert symbols == {"gyrA"}
    assert evidence[0]["accepted"] is True
    assert evidence[1]["accepted"] is False
    assert evidence[2]["accepted"] is False
