from __future__ import annotations

from resistsense.curation import SPLIT_PROPORTIONS, assign_group_partitions


def test_multilabel_partition_is_deterministic_and_group_safe() -> None:
    records = []
    antibiotics = ("ampicillin", "ciprofloxacin")
    for group_index in range(40):
        for sample_index in range(2):
            label = "resistant" if sample_index == 0 else "susceptible"
            records.append(
                {
                    "sample_id": f"sample-{group_index}-{sample_index}",
                    "genetic_group": f"group-{group_index}",
                    "labels": {antibiotic: label for antibiotic in antibiotics},
                }
            )

    first = assign_group_partitions(records)
    second = assign_group_partitions(list(reversed(records)))

    assert first == second
    assert set(first.values()) == set(SPLIT_PROPORTIONS)
    for group in {record["genetic_group"] for record in records}:
        assert isinstance(first[group], str)
