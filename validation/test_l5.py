"""L5 — Orchestration / saga engine (agent-sre): saga, off-policy step, cross-team
delegation, circuit breaker.

Owner: Vamsi+Lok+Laxmi. There is no L5 service in the local demo bring-up, so
every row needs ASL_ORCHESTRATOR_URL and skips here. Assertions target the saga
API so owners only need to point ASL_ORCHESTRATOR_URL at a live orchestrator.
"""

from __future__ import annotations

import os

import pytest

from conftest import http, params_for, require_live

SAGA_BODY = {
    "saga": "flight-disruption-rebooking", "team_id": "AA-OPS",
    "session_id": "val-l5-001",
    "input": {"flight": "AA100", "record_locator": "ABC123"},
}


def _base() -> str:
    return os.environ["ASL_ORCHESTRATOR_URL"].rstrip("/")


def _run(body: dict) -> tuple[int, object]:
    return http("POST", f"{_base()}/api/v1/sagas/run", body, timeout=30.0)


def _steps(resp) -> list:
    return resp.get("steps", []) if isinstance(resp, dict) else []


@pytest.mark.parametrize("row", params_for("L5"))
def test_l5(row):
    require_live(row.needs, row.owner)

    if row.variant == "HAPPY":
        status, resp = _run(SAGA_BODY)
        assert resp.get("status") == "completed" and _steps(resp), row.expected

    elif row.variant == "ADVERSARIAL":  # off-policy step blocked
        body = {**SAGA_BODY, "inject_step": {"tool": "competitor-fare-lookup"}}
        _, resp = _run(body)
        blocked = [s for s in _steps(resp) if s.get("status") == "blocked"]
        assert blocked, row.expected

    elif row.variant == "ISOLATION":  # cross-team delegation denied
        body = {**SAGA_BODY, "delegate_to": {"team_id": "AA-CARGO"}}
        status, resp = _run(body)
        assert status in (403,) or resp.get("status") == "denied", row.expected

    elif row.variant == "FAILURE_INJECTION":  # circuit breaker + compensation
        body = {**SAGA_BODY, "fault": {"dependency": "rebook-service", "code": 500}}
        _, resp = _run(body)
        assert resp.get("circuit_breaker") == "open"
        assert any(s.get("type") == "compensation" for s in _steps(resp)), row.expected
