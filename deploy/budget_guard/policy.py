from __future__ import annotations


def should_close_public_access(
    event: dict,
    expected_budget_name: str,
) -> bool:
    if event.get("budgetDisplayName") != expected_budget_name:
        return False
    try:
        cost = float(event["costAmount"])
        budget = float(event["budgetAmount"])
    except (KeyError, TypeError, ValueError):
        return False
    return budget > 0 and cost >= budget


def remove_public_invoker(policy: dict) -> tuple[dict, bool]:
    changed = False
    retained_bindings: list[dict] = []
    for binding in policy.get("bindings", []):
        if binding.get("role") != "roles/run.invoker":
            retained_bindings.append(binding)
            continue
        members = [member for member in binding.get("members", []) if member != "allUsers"]
        if len(members) != len(binding.get("members", [])):
            changed = True
        if members:
            retained_bindings.append({**binding, "members": members})
    return {**policy, "bindings": retained_bindings}, changed
