"""L6 — Agent Registry + Marketplace Reviewer: verdict, injection detection,
auth gating, dedup fail-closed.

Owner: Niranjan+Pradeep. Behavioral. Skips in this env (reviewer + Azure Search
absent). Three rows encode audit gaps (xfail): injection not detected,
/review-submission accepts unauthenticated calls, dedup skipped-yet-approved.
"""

from __future__ import annotations

import pytest

from conftest import params_for, perform, require_live


@pytest.mark.parametrize("row", params_for("L6"))
def test_l6(row):
    require_live(row.needs, row.owner)
    status, resp = perform(row)

    if row.variant == "HAPPY":
        assert isinstance(resp, dict) and "decision" in resp, row.expected

    elif row.variant == "ADVERSARIAL":  # injection must be detected
        assert resp.get("content_guardrail_injection_detected") is True, row.expected

    elif row.variant == "ISOLATION":  # unauthenticated submit must be refused
        assert status in (401, 403), f"{row.expected} — got status {status}"

    elif row.variant == "FAILURE_INJECTION":  # dedup down must not auto-approve
        dedup = resp.get("duplicate_detection", {}) if isinstance(resp, dict) else {}
        if dedup.get("checked") is False:
            assert resp.get("decision") != "approved", row.expected
