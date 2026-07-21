from uuid import UUID

from resistsense.usage_counter import (
    hash_anonymous_visitor,
    record_anonymous_visitor,
    usage_summary,
)


VISITOR_ID = UUID("c5690b0f-207c-45a8-bf05-daf30f5303a9")


class MemoryUsageStore:
    def __init__(self) -> None:
        self.visitors: set[str] = set()

    def record(self, visitor_hash: str) -> tuple[int, bool]:
        before = len(self.visitors)
        self.visitors.add(visitor_hash)
        return len(self.visitors), len(self.visitors) > before

    def summary(self) -> int:
        return len(self.visitors)


class FailingUsageStore:
    def record(self, visitor_hash: str) -> tuple[int, bool]:
        raise RuntimeError("simulated storage outage")

    def summary(self) -> int:
        raise RuntimeError("simulated storage outage")


def test_hash_is_stable_and_does_not_retain_raw_identifier() -> None:
    first = hash_anonymous_visitor(VISITOR_ID)
    second = hash_anonymous_visitor(str(VISITOR_ID))
    assert first == second
    assert len(first) == 64
    assert str(VISITOR_ID) not in first


def test_counter_deduplicates_the_same_anonymous_browser() -> None:
    store = MemoryUsageStore()
    first = record_anonymous_visitor(VISITOR_ID, store)
    second = record_anonymous_visitor(VISITOR_ID, store)
    assert first["unique_anonymous_browsers"] == 1
    assert first["new_visitor"] is True
    assert second["unique_anonymous_browsers"] == 1
    assert second["new_visitor"] is False
    assert usage_summary(store)["unique_anonymous_browsers"] == 1


def test_counter_failure_never_breaks_the_research_app() -> None:
    result = record_anonymous_visitor(VISITOR_ID, FailingUsageStore())
    assert result["available"] is False
    assert result["reason"] == "storage_unavailable"
    assert result["unique_anonymous_browsers"] is None


def test_counter_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("RESISTSENSE_USAGE_COUNTER_ENABLED", raising=False)
    result = record_anonymous_visitor(VISITOR_ID)
    assert result["available"] is False
    assert result["reason"] == "counter_disabled"
