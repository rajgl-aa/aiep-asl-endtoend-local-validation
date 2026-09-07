"""L1 — Sentinel PII-mask, Model Axis auth, ASL DB Gateway table isolation.

Owner: Lok+Vijay. Behavioral, not liveness. In this env everything skips
(needs-live-env) because the L1 services and the Apigee bearer are absent.
"""

from __future__ import annotations

import json

import pytest

from conftest import S, http, params_for, perform, require_live


def _flagged(resp) -> bool:
    """True if a scan response marks the input unsafe / injection-detected."""
    blob = json.dumps(resp).lower()
    return any(k in blob for k in ('"injection": true', '"blocked": true',
                                   '"safe": false', '"flagged": true',
                                   '"is_injection": true', '"unsafe": true'))


def _rows(resp) -> list:
    if isinstance(resp, dict):
        return resp.get("rows") or resp.get("results") or resp.get("data") or []
    return resp if isinstance(resp, list) else []


@pytest.mark.parametrize("row", params_for("L1"))
def test_l1(row):
    require_live(row.needs, row.owner)
    status, resp = perform(row)

    if row.variant == "HAPPY":  # PII masked before the model hop
        assert "jane.doe@example.com" not in json.dumps(resp), row.expected
        assert "987654321" not in json.dumps(resp), row.expected

    elif row.variant == "ADVERSARIAL":  # injection flagged
        assert _flagged(resp), f"{row.expected} — got {resp}"

    elif row.variant == "ISOLATION":  # foreign table denied / empty
        assert status == 403 or not _rows(resp), row.expected

    elif row.variant == "FAILURE_INJECTION":  # fail-closed without Apigee bearer
        assert status in (401, 403), f"{row.expected} — got status {status}"
