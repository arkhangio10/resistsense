from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .config import OpenAIUsageGuardConfig
from .usage_counter import hash_anonymous_visitor


USAGE_COLLECTION = "resistsense_openai_usage"
DAILY_VISITOR_COLLECTION = "daily_browser_usage"
RESERVATION_COLLECTION = "reservations"
MICRO_USD_PER_USD = 1_000_000

QuotaReason = Literal[
    "guard_disabled",
    "visitor_id_missing",
    "payload_too_large",
    "daily_limit_reached",
    "monthly_budget_reached",
    "storage_unavailable",
]


class AuditQuotaStatus(BaseModel):
    enabled: bool
    available: bool
    month_utc: str
    monthly_budget_usd: float
    allocated_usd: float | None = Field(default=None, ge=0)
    remaining_usd: float | None = Field(default=None, ge=0)
    daily_request_limit: int = Field(ge=1)
    daily_requests_used: int | None = Field(default=None, ge=0)
    daily_requests_remaining: int | None = Field(default=None, ge=0)
    reason: QuotaReason | None = None
    privacy: str = (
        "Only a one-way hash of the anonymous browser UUID is used for quota control; "
        "no IP address, FASTA, filename, or personal data is stored."
    )


@dataclass(frozen=True)
class AuditQuotaDecision:
    allowed: bool
    reservation_id: str | None
    reason: QuotaReason | None
    status: AuditQuotaStatus


class OpenAIUsageStore(Protocol):
    def reserve(
        self,
        visitor_hash: str,
        now: datetime,
        policy: OpenAIUsageGuardConfig,
    ) -> AuditQuotaDecision: ...

    def settle(
        self,
        reservation_id: str,
        now: datetime,
        policy: OpenAIUsageGuardConfig,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None: ...

    def summary(
        self,
        visitor_hash: str,
        now: datetime,
        policy: OpenAIUsageGuardConfig,
    ) -> AuditQuotaStatus: ...


def usage_guard_enabled(policy: OpenAIUsageGuardConfig) -> bool:
    environment_enabled = os.getenv(
        "RESISTSENSE_OPENAI_USAGE_GUARD_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    return policy.enabled and environment_enabled


def _month_key(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m")


def _day_key(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _micro_usd(value: float) -> int:
    return math.ceil(value * MICRO_USD_PER_USD)


def _usd(value: int) -> float:
    return round(value / MICRO_USD_PER_USD, 6)


def _actual_cost_micro_usd(
    input_tokens: int | None,
    output_tokens: int | None,
    policy: OpenAIUsageGuardConfig,
) -> int | None:
    if input_tokens is None or output_tokens is None:
        return None
    if input_tokens < 0 or output_tokens < 0:
        return None
    # At per-million-token pricing, each rate is also the number of micro-USD
    # charged per token. Charging all input at the uncached rate is conservative.
    return math.ceil(
        input_tokens * policy.input_usd_per_million_tokens
        + output_tokens * policy.output_usd_per_million_tokens
    )


def evaluate_quota_reservation(
    allocated_micro_usd: int,
    daily_used: int,
    policy: OpenAIUsageGuardConfig,
) -> tuple[bool, QuotaReason | None, int, int]:
    if daily_used >= policy.daily_requests_per_browser:
        return False, "daily_limit_reached", allocated_micro_usd, daily_used
    reservation = _micro_usd(policy.reservation_usd)
    if allocated_micro_usd + reservation > _micro_usd(policy.monthly_budget_usd):
        return False, "monthly_budget_reached", allocated_micro_usd, daily_used
    return True, None, allocated_micro_usd + reservation, daily_used + 1


def settle_quota_allocation(
    allocated_micro_usd: int,
    reserved_micro_usd: int,
    input_tokens: int | None,
    output_tokens: int | None,
    policy: OpenAIUsageGuardConfig,
) -> tuple[int, int]:
    actual = _actual_cost_micro_usd(input_tokens, output_tokens, policy)
    charged = reserved_micro_usd if actual is None else max(0, actual)
    return max(0, allocated_micro_usd + charged - reserved_micro_usd), charged


def _status(
    *,
    now: datetime,
    policy: OpenAIUsageGuardConfig,
    allocated_micro_usd: int | None,
    daily_used: int | None,
    available: bool,
    reason: QuotaReason | None = None,
) -> AuditQuotaStatus:
    budget = _micro_usd(policy.monthly_budget_usd)
    remaining = (
        max(0, budget - allocated_micro_usd)
        if allocated_micro_usd is not None
        else None
    )
    daily_remaining = (
        max(0, policy.daily_requests_per_browser - daily_used)
        if daily_used is not None
        else None
    )
    return AuditQuotaStatus(
        enabled=True,
        available=available,
        month_utc=_month_key(now),
        monthly_budget_usd=policy.monthly_budget_usd,
        allocated_usd=(
            _usd(allocated_micro_usd)
            if allocated_micro_usd is not None
            else None
        ),
        remaining_usd=_usd(remaining) if remaining is not None else None,
        daily_request_limit=policy.daily_requests_per_browser,
        daily_requests_used=daily_used,
        daily_requests_remaining=daily_remaining,
        reason=reason,
    )


def blocked_quota_status(
    policy: OpenAIUsageGuardConfig,
    reason: QuotaReason,
    *,
    now: datetime | None = None,
) -> AuditQuotaStatus:
    current = now or datetime.now(timezone.utc)
    return _status(
        now=current,
        policy=policy,
        allocated_micro_usd=None,
        daily_used=None,
        available=False,
        reason=reason,
    )


class FirestoreOpenAIUsageStore:
    def __init__(self) -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self._client = firestore.Client()
        self._collection = self._client.collection(USAGE_COLLECTION)

    def _references(self, visitor_hash: str, now: datetime):
        month_ref = self._collection.document(_month_key(now))
        daily_ref = month_ref.collection(DAILY_VISITOR_COLLECTION).document(
            f"{_day_key(now)}-{visitor_hash}"
        )
        return month_ref, daily_ref

    def reserve(
        self,
        visitor_hash: str,
        now: datetime,
        policy: OpenAIUsageGuardConfig,
    ) -> AuditQuotaDecision:
        month_ref, daily_ref = self._references(visitor_hash, now)
        reservation_id = uuid4().hex
        reservation_ref = month_ref.collection(RESERVATION_COLLECTION).document(
            reservation_id
        )
        reservation = _micro_usd(policy.reservation_usd)
        transaction = self._client.transaction()

        @self._firestore.transactional
        def reserve_once(active_transaction):
            month_snapshot = month_ref.get(transaction=active_transaction)
            daily_snapshot = daily_ref.get(transaction=active_transaction)
            month_values = month_snapshot.to_dict() or {}
            daily_values = daily_snapshot.to_dict() or {}
            allocated = int(month_values.get("allocated_micro_usd", 0))
            daily_used = int(daily_values.get("requests", 0))

            allowed, reason, new_allocated, new_daily_used = (
                evaluate_quota_reservation(allocated, daily_used, policy)
            )
            if not allowed:
                return False, reason, allocated, daily_used

            active_transaction.set(
                month_ref,
                {
                    "allocated_micro_usd": new_allocated,
                    "request_attempts": self._firestore.Increment(1),
                    "updated_at": self._firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            active_transaction.set(
                daily_ref,
                {
                    "requests": new_daily_used,
                    "updated_at": self._firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            active_transaction.set(
                reservation_ref,
                {
                    "status": "reserved",
                    "reserved_micro_usd": reservation,
                    "created_at": self._firestore.SERVER_TIMESTAMP,
                },
            )
            return True, None, new_allocated, new_daily_used

        allowed, reason, allocated, daily_used = reserve_once(transaction)
        status = _status(
            now=now,
            policy=policy,
            allocated_micro_usd=allocated,
            daily_used=daily_used,
            available=True,
            reason=reason,
        )
        return AuditQuotaDecision(
            allowed=allowed,
            reservation_id=reservation_id if allowed else None,
            reason=reason,
            status=status,
        )

    def settle(
        self,
        reservation_id: str,
        now: datetime,
        policy: OpenAIUsageGuardConfig,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        month_ref = self._collection.document(_month_key(now))
        reservation_ref = month_ref.collection(RESERVATION_COLLECTION).document(
            reservation_id
        )
        transaction = self._client.transaction()

        @self._firestore.transactional
        def settle_once(active_transaction):
            reservation_snapshot = reservation_ref.get(transaction=active_transaction)
            month_snapshot = month_ref.get(transaction=active_transaction)
            reservation_values = reservation_snapshot.to_dict() or {}
            month_values = month_snapshot.to_dict() or {}
            allocated = int(month_values.get("allocated_micro_usd", 0))
            if reservation_values.get("status") != "reserved":
                return allocated

            reserved = int(reservation_values.get("reserved_micro_usd", 0))
            adjusted, charged = settle_quota_allocation(
                allocated,
                reserved,
                input_tokens,
                output_tokens,
                policy,
            )
            active_transaction.set(
                month_ref,
                {
                    "allocated_micro_usd": adjusted,
                    "completed_requests": self._firestore.Increment(1),
                    "input_tokens": self._firestore.Increment(input_tokens or 0),
                    "output_tokens": self._firestore.Increment(output_tokens or 0),
                    "reservation_exceeded": self._firestore.Increment(
                        1 if charged > reserved else 0
                    ),
                    "updated_at": self._firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            active_transaction.set(
                reservation_ref,
                {
                    "status": "settled",
                    "charged_micro_usd": charged,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "settled_at": self._firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            return adjusted

        settle_once(transaction)

    def summary(
        self,
        visitor_hash: str,
        now: datetime,
        policy: OpenAIUsageGuardConfig,
    ) -> AuditQuotaStatus:
        month_ref, daily_ref = self._references(visitor_hash, now)
        month_values = month_ref.get().to_dict() or {}
        daily_values = daily_ref.get().to_dict() or {}
        return _status(
            now=now,
            policy=policy,
            allocated_micro_usd=int(month_values.get("allocated_micro_usd", 0)),
            daily_used=int(daily_values.get("requests", 0)),
            available=True,
        )


@lru_cache(maxsize=1)
def firestore_openai_usage_store() -> FirestoreOpenAIUsageStore:
    return FirestoreOpenAIUsageStore()


def reserve_openai_audit(
    visitor_id: UUID | str,
    policy: OpenAIUsageGuardConfig,
    *,
    store: OpenAIUsageStore | None = None,
    now: datetime | None = None,
) -> AuditQuotaDecision:
    current = now or datetime.now(timezone.utc)
    if not usage_guard_enabled(policy) and store is None:
        status = AuditQuotaStatus(
            enabled=False,
            available=False,
            month_utc=_month_key(current),
            monthly_budget_usd=policy.monthly_budget_usd,
            daily_request_limit=policy.daily_requests_per_browser,
            reason="guard_disabled",
        )
        return AuditQuotaDecision(False, None, "guard_disabled", status)
    try:
        visitor_hash = hash_anonymous_visitor(visitor_id)
        active_store = store or firestore_openai_usage_store()
        return active_store.reserve(visitor_hash, current, policy)
    except Exception:
        status = blocked_quota_status(policy, "storage_unavailable", now=current)
        return AuditQuotaDecision(False, None, "storage_unavailable", status)


def settle_openai_audit(
    reservation_id: str,
    visitor_id: UUID | str,
    policy: OpenAIUsageGuardConfig,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    store: OpenAIUsageStore | None = None,
    now: datetime | None = None,
) -> AuditQuotaStatus:
    current = now or datetime.now(timezone.utc)
    try:
        active_store = store or firestore_openai_usage_store()
        active_store.settle(
            reservation_id,
            current,
            policy,
            input_tokens,
            output_tokens,
        )
        return active_store.summary(
            hash_anonymous_visitor(visitor_id), current, policy
        )
    except Exception:
        # The full reservation remains allocated when settlement fails, which is
        # intentionally fail-safe for spending control.
        return blocked_quota_status(policy, "storage_unavailable", now=current)
