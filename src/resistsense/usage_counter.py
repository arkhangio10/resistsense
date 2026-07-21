from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from typing import Protocol
from uuid import UUID


COUNTER_COLLECTION = "resistsense_usage"
SUMMARY_DOCUMENT = "summary"
VISITOR_SUBCOLLECTION = "anonymous_browsers"
HASH_NAMESPACE = "resistsense-anonymous-browser-v1"


class UsageStore(Protocol):
    def record(self, visitor_hash: str) -> tuple[int, bool]: ...

    def summary(self) -> int: ...


def counter_enabled() -> bool:
    return os.getenv("RESISTSENSE_USAGE_COUNTER_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def hash_anonymous_visitor(visitor_id: UUID | str) -> str:
    canonical = str(UUID(str(visitor_id)))
    return hashlib.sha256(f"{HASH_NAMESPACE}:{canonical}".encode()).hexdigest()


class FirestoreUsageStore:
    def __init__(self) -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self._client = firestore.Client()
        self._summary_ref = self._client.collection(COUNTER_COLLECTION).document(
            SUMMARY_DOCUMENT
        )

    def record(self, visitor_hash: str) -> tuple[int, bool]:
        visitor_ref = self._summary_ref.collection(VISITOR_SUBCOLLECTION).document(
            visitor_hash
        )
        transaction = self._client.transaction()

        @self._firestore.transactional
        def insert_once(active_transaction) -> bool:
            if visitor_ref.get(transaction=active_transaction).exists:
                return False
            active_transaction.set(
                visitor_ref,
                {"created_at": self._firestore.SERVER_TIMESTAMP},
            )
            active_transaction.set(
                self._summary_ref,
                {
                    "unique_anonymous_browsers": self._firestore.Increment(1),
                    "updated_at": self._firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            return True

        created = insert_once(transaction)
        return self.summary(), created

    def summary(self) -> int:
        snapshot = self._summary_ref.get()
        if not snapshot.exists:
            return 0
        return int((snapshot.to_dict() or {}).get("unique_anonymous_browsers", 0))


@lru_cache(maxsize=1)
def firestore_usage_store() -> FirestoreUsageStore:
    return FirestoreUsageStore()


def unavailable_summary(reason: str) -> dict:
    return {
        "available": False,
        "unique_anonymous_browsers": None,
        "new_visitor": None,
        "reason": reason,
        "privacy": "The application stores no IP address, FASTA, filename, or personal data.",
    }


def record_anonymous_visitor(
    visitor_id: UUID | str,
    store: UsageStore | None = None,
) -> dict:
    if not counter_enabled() and store is None:
        return unavailable_summary("counter_disabled")
    visitor_hash = hash_anonymous_visitor(visitor_id)
    try:
        active_store = store or firestore_usage_store()
        count, created = active_store.record(visitor_hash)
    except Exception:
        return unavailable_summary("storage_unavailable")
    return {
        "available": True,
        "unique_anonymous_browsers": count,
        "new_visitor": created,
        "reason": None,
        "privacy": "The application stores no IP address, FASTA, filename, or personal data.",
    }


def usage_summary(store: UsageStore | None = None) -> dict:
    if not counter_enabled() and store is None:
        return unavailable_summary("counter_disabled")
    try:
        active_store = store or firestore_usage_store()
        count = active_store.summary()
    except Exception:
        return unavailable_summary("storage_unavailable")
    return {
        "available": True,
        "unique_anonymous_browsers": count,
        "new_visitor": None,
        "reason": None,
        "privacy": "The application stores no IP address, FASTA, filename, or personal data.",
    }
