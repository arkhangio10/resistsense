from datetime import datetime, timezone

from resistsense.config import OpenAIUsageGuardConfig
from resistsense.openai_usage_guard import (
    AuditQuotaDecision,
    AuditQuotaStatus,
    evaluate_quota_reservation,
    reserve_openai_audit,
    settle_quota_allocation,
)


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
VISITOR_ID = "c5690b0f-207c-45a8-bf05-daf30f5303a9"


def _policy() -> OpenAIUsageGuardConfig:
    return OpenAIUsageGuardConfig(
        monthly_budget_usd=5.0,
        daily_requests_per_browser=3,
        reservation_usd=0.50,
        input_usd_per_million_tokens=6.25,
        output_usd_per_million_tokens=30.0,
    )


def test_quota_reservation_enforces_daily_and_monthly_limits() -> None:
    policy = _policy()
    allowed, reason, allocated, daily = evaluate_quota_reservation(0, 0, policy)
    assert allowed is True
    assert reason is None
    assert allocated == 500_000
    assert daily == 1

    daily_block = evaluate_quota_reservation(0, 3, policy)
    assert daily_block[:2] == (False, "daily_limit_reached")

    monthly_block = evaluate_quota_reservation(4_600_000, 0, policy)
    assert monthly_block[:2] == (False, "monthly_budget_reached")


def test_successful_settlement_releases_unused_reservation() -> None:
    adjusted, charged = settle_quota_allocation(
        allocated_micro_usd=500_000,
        reserved_micro_usd=500_000,
        input_tokens=120,
        output_tokens=80,
        policy=_policy(),
    )
    assert charged == 3_150
    assert adjusted == 3_150


def test_unknown_usage_keeps_full_reservation_fail_safe() -> None:
    adjusted, charged = settle_quota_allocation(
        allocated_micro_usd=500_000,
        reserved_micro_usd=500_000,
        input_tokens=None,
        output_tokens=None,
        policy=_policy(),
    )
    assert charged == 500_000
    assert adjusted == 500_000


class CapturingStore:
    def __init__(self) -> None:
        self.visitor_hash: str | None = None

    def reserve(self, visitor_hash, now, policy):
        self.visitor_hash = visitor_hash
        return AuditQuotaDecision(
            allowed=True,
            reservation_id="reservation-1",
            reason=None,
            status=AuditQuotaStatus(
                enabled=True,
                available=True,
                month_utc="2026-07",
                monthly_budget_usd=5.0,
                allocated_usd=0.5,
                remaining_usd=4.5,
                daily_request_limit=3,
                daily_requests_used=1,
                daily_requests_remaining=2,
            ),
        )

    def settle(self, *args, **kwargs):
        return None

    def summary(self, *args, **kwargs):
        raise AssertionError("summary is not needed in this test")


def test_reservation_hashes_browser_uuid_before_storage() -> None:
    store = CapturingStore()
    decision = reserve_openai_audit(VISITOR_ID, _policy(), store=store, now=NOW)
    assert decision.allowed is True
    assert store.visitor_hash is not None
    assert len(store.visitor_hash) == 64
    assert VISITOR_ID not in store.visitor_hash
