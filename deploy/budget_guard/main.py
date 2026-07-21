from __future__ import annotations

import base64
import json
import logging
import os
import time
from urllib.parse import quote

import functions_framework
import google.auth
from google.auth.transport.requests import AuthorizedSession

from policy import remove_public_invoker, should_close_public_access


LOGGER = logging.getLogger(__name__)


def _decode_budget_event(cloud_event) -> dict:
    encoded = cloud_event.data.get("message", {}).get("data")
    if not encoded:
        return {}
    try:
        decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        LOGGER.warning("Ignoring malformed budget notification")
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _close_public_access(project_id: str, region: str, service: str) -> bool:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    resource = f"projects/{project_id}/locations/{region}/services/{service}"
    escaped_resource = quote(resource, safe="/")
    ingress_url = (
        f"https://run.googleapis.com/v2/{escaped_resource}?updateMask=ingress"
    )
    ingress_response = session.patch(
        ingress_url,
        json={
            "name": resource,
            "ingress": "INGRESS_TRAFFIC_INTERNAL_ONLY",
        },
        timeout=30,
    )
    ingress_response.raise_for_status()
    operation_name = ingress_response.json().get("name")
    if operation_name:
        operation_url = (
            f"https://run.googleapis.com/v2/{quote(operation_name, safe='/')}"
        )
        for _ in range(20):
            operation_response = session.get(operation_url, timeout=30)
            operation_response.raise_for_status()
            operation = operation_response.json()
            if operation.get("done"):
                if operation.get("error"):
                    raise RuntimeError(f"Cloud Run ingress update failed: {operation['error']}")
                break
            time.sleep(2)

    policy_url = f"https://run.googleapis.com/v1/{escaped_resource}:getIamPolicy"
    response = session.get(policy_url, timeout=30)
    response.raise_for_status()
    policy, changed = remove_public_invoker(response.json())
    if not changed:
        LOGGER.info("Ingress restricted; public IAM was already closed for %s", resource)
        return False

    update_url = f"https://run.googleapis.com/v1/{escaped_resource}:setIamPolicy"
    response = session.post(update_url, json={"policy": policy}, timeout=30)
    response.raise_for_status()
    LOGGER.warning("Budget reached: ingress and public IAM closed for %s", resource)
    return True


@functions_framework.cloud_event
def handle_budget_event(cloud_event) -> None:
    event = _decode_budget_event(cloud_event)
    expected_budget_name = os.environ["EXPECTED_BUDGET_NAME"]
    if not should_close_public_access(event, expected_budget_name):
        LOGGER.info(
            "No shutdown action for budget=%s cost=%s limit=%s",
            event.get("budgetDisplayName"),
            event.get("costAmount"),
            event.get("budgetAmount"),
        )
        return
    _close_public_access(
        os.environ["TARGET_PROJECT_ID"],
        os.environ["TARGET_REGION"],
        os.environ["TARGET_SERVICE"],
    )
