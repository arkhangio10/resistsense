from resistsense.config import load_config
from resistsense.pipeline import analyze_fasta
from resistsense.reporter import audit_report


def test_incomplete_runtime_returns_auditable_no_calls() -> None:
    config = load_config("configs/resistsense.yaml")
    response = analyze_fasta(b">short\nACGTACGT\n", "short.fasta", config)
    assert all(result.final_status.value == "no_call" for result in response.results)
    assert audit_report(response) == []
