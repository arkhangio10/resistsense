from resistsense.schemas import MarkerEvidence, TargetStatus
from resistsense.targets import evaluate_target, load_target_catalog, relevant_markers


def test_dual_target_requires_both_components() -> None:
    catalog = load_target_catalog()
    partial, _ = evaluate_target(
        "trimethoprim/sulfamethoxazole", {"folA"}, catalog
    )
    complete, _ = evaluate_target(
        "trimethoprim/sulfamethoxazole", {"folA", "folP"}, catalog
    )
    assert partial is TargetStatus.ABSENT
    assert complete is TargetStatus.PRESENT


def test_markers_are_filtered_to_the_antibiotic_class() -> None:
    catalog = load_target_catalog()
    target = catalog.antibiotics["ciprofloxacin"]
    markers = relevant_markers(
        [
            MarkerEvidence(
                symbol="gyrA_S83L",
                subtype="POINT",
                resistance_class="QUINOLONE",
            ),
            MarkerEvidence(
                symbol="blaCTX-M-15",
                subtype="AMR",
                resistance_class="BETA-LACTAM",
            ),
        ],
        target,
    )
    assert [marker.symbol for marker in markers] == ["gyrA_S83L"]


def test_cefotaxime_uses_amrfinder_subclass_not_broad_beta_lactam_class() -> None:
    catalog = load_target_catalog()
    target = catalog.antibiotics["cefotaxime"]
    markers = relevant_markers(
        [
            MarkerEvidence(
                symbol="blaEC",
                subtype="AMR",
                resistance_class="BETA-LACTAM",
                subclass="BETA-LACTAM",
            ),
            MarkerEvidence(
                symbol="blaCTX-M-15",
                subtype="AMR",
                resistance_class="BETA-LACTAM",
                subclass="CEPHALOSPORIN",
            ),
        ],
        target,
    )
    assert [marker.symbol for marker in markers] == ["blaCTX-M-15"]


def test_gentamicin_excludes_streptomycin_only_markers() -> None:
    catalog = load_target_catalog()
    target = catalog.antibiotics["gentamicin"]
    markers = relevant_markers(
        [
            MarkerEvidence(
                symbol="aadA5",
                subtype="AMR",
                resistance_class="AMINOGLYCOSIDE",
                subclass="STREPTOMYCIN",
            ),
            MarkerEvidence(
                symbol="aac(3)-IId",
                subtype="AMR",
                resistance_class="AMINOGLYCOSIDE",
                subclass="GENTAMICIN",
            ),
        ],
        target,
    )
    assert [marker.symbol for marker in markers] == ["aac(3)-IId"]
