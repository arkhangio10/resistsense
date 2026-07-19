from resistsense.kmers import hashed_kmer_mapping


def test_hashed_kmers_are_normalized_and_strand_invariant() -> None:
    forward = b">x\nACGTACCA\n"
    reverse_complement = b">x\nTGGTACGT\n"
    first = hashed_kmer_mapping(forward, k=7, buckets=32, stride=1)
    second = hashed_kmer_mapping(reverse_complement, k=7, buckets=32, stride=1)
    assert first
    assert first == second
    assert abs(sum(first.values()) - 1.0) < 1e-9


def test_ambiguous_kmer_windows_are_skipped() -> None:
    mapping = hashed_kmer_mapping(b">x\nNNNNNNNNNN\n", k=7, buckets=32, stride=1)
    assert mapping == {}
