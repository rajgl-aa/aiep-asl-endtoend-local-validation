"""L3 — Policy Engine: allow, competitor-block, team scope, fail-closed parse.

Owner: Vamsi. Behavioral. Skips in this env (policy engine absent).
The FAILURE_INJECTION row encodes the audit finding that an unparseable policy
condition currently fails OPEN; it is marked xfail so a run against the current
deployed path records the gap rather than a hard failure.
"""

from __future__ import annotations

import pytest

from conftest import params_for, perform, require_live


def _triggered(resp) -> list:
    return resp.get("triggered", []) if isinstance(resp, dict) else []


def _evaluated(resp) -> list:
    if not isinstance(resp, dict):
        return []
    return _triggered(resp) + resp.get("skipped", [])


def _has_block(resp) -> bool:
    return any(r.get("action") == "block" for r in _triggered(resp))


@pytest.mark.parametrize("row", params_for("L3"))
def test_l3(row):
    require_live(row.needs, row.owner)
    _, resp = perform(row)

    if row.variant == "HAPPY":  # AA-related -> allow
        assert not _has_block(resp), f"{row.expected} — got {_triggered(resp)}"

    elif row.variant == "ADVERSARIAL":  # competitor -> block (law-004)
        assert _has_block(resp), f"{row.expected} — got {_triggered(resp)}"

    elif row.variant == "ISOLATION":  # no foreign-team policy considered
        foreign = [p for p in _evaluated(resp)
                   if p.get("policy_scope") not in (None, "org", "AA-CARGO")]
        assert not foreign, f"{row.expected} — foreign-scope policy leaked: {foreign}"

    elif row.variant == "FAILURE_INJECTION":  # unparseable condition must fail CLOSED
        assert _has_block(resp), \
            "unparseable/errored policy condition must fail CLOSED (block), not allow"
