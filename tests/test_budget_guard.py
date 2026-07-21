import importlib.util
from pathlib import Path


POLICY_PATH = Path(__file__).resolve().parents[1] / "deploy" / "budget_guard" / "policy.py"
SPEC = importlib.util.spec_from_file_location("budget_guard_policy", POLICY_PATH)
assert SPEC and SPEC.loader
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def test_budget_guard_acts_only_at_the_exact_named_limit() -> None:
    event = {
        "budgetDisplayName": "ResistSense demo budget",
        "budgetAmount": "10.0",
        "costAmount": "9.99",
    }
    assert not POLICY.should_close_public_access(event, "ResistSense demo budget")
    event["costAmount"] = "10.0"
    assert POLICY.should_close_public_access(event, "ResistSense demo budget")
    assert not POLICY.should_close_public_access(event, "Another budget")


def test_budget_guard_ignores_invalid_or_out_of_order_payloads() -> None:
    assert not POLICY.should_close_public_access({}, "ResistSense demo budget")
    assert not POLICY.should_close_public_access(
        {
            "budgetDisplayName": "ResistSense demo budget",
            "budgetAmount": "10",
            "costAmount": "not-a-number",
        },
        "ResistSense demo budget",
    )


def test_public_invoker_removal_is_selective_and_idempotent() -> None:
    original = {
        "etag": "abc",
        "bindings": [
            {
                "role": "roles/run.invoker",
                "members": ["allUsers", "user:owner@example.com"],
            },
            {"role": "roles/viewer", "members": ["user:owner@example.com"]},
        ],
    }
    updated, changed = POLICY.remove_public_invoker(original)
    assert changed is True
    assert updated["etag"] == "abc"
    assert updated["bindings"] == [
        {
            "role": "roles/run.invoker",
            "members": ["user:owner@example.com"],
        },
        {"role": "roles/viewer", "members": ["user:owner@example.com"]},
    ]
    repeated, changed_again = POLICY.remove_public_invoker(updated)
    assert changed_again is False
    assert repeated == updated
