from resistsense.config import FastaQcConfig
from resistsense.fasta import validate_fasta
from resistsense.features import feature_mapping
from resistsense.schemas import MarkerEvidence


def test_model_features_exclude_plus_virulence_markers() -> None:
    policy = FastaQcConfig(
        min_genome_length_bp=1,
        max_genome_length_bp=100,
        max_contigs=5,
        max_ambiguous_fraction=0.1,
        allowed_bases="ACGTN",
    )
    qc = validate_fasta(b">x\nACGT\n", "x.fna", policy)
    mapping = feature_mapping(
        [
            MarkerEvidence(symbol="blaCTX-M-15", element_type="AMR"),
            MarkerEvidence(
                symbol="iss",
                element_type="AMR",
                subtype="VIRULENCE",
            ),
        ],
        qc,
    )
    assert mapping["marker__blactx-m-15"] == 1.0
    assert "marker__iss" not in mapping
