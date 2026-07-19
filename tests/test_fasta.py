from resistsense.config import FastaQcConfig
from resistsense.fasta import parse_fasta, validate_fasta


POLICY = FastaQcConfig(
    min_genome_length_bp=8,
    max_genome_length_bp=100,
    max_contigs=3,
    max_ambiguous_fraction=0.1,
    allowed_bases="ACGTN",
)


def test_multicontig_fasta_passes_policy() -> None:
    content = b">contig-1\nACGTACGT\n>contig-2\nACGT\n"
    records = parse_fasta(content)
    report = validate_fasta(content, "sample.fna", POLICY)
    assert len(records) == 2
    assert report.passed is True
    assert report.total_length_bp == 12


def test_invalid_sequence_fails_closed() -> None:
    report = validate_fasta(b">x\nACGTZACGT\n", "bad.fasta", POLICY)
    assert report.passed is False
    assert report.invalid_characters == ["Z"]


def test_plain_sequence_without_header_is_rejected() -> None:
    report = validate_fasta(b"ACGTACGT", "bad.fasta", POLICY)
    assert report.passed is False
    assert "before FASTA header" in report.reasons[0]
