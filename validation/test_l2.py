"""L2 — Federated Retrieval Gateway: serving, PII-quarantine, tenant isolation.

Owner: Vijay. Behavioral. Skips in this env (gateway + pgvector absent).
"""

from __future__ import annotations

import pytest

from conftest import params_for, perform, require_live


def _chunks(resp) -> list:
    results = resp.get("results", []) if isinstance(resp, dict) else []
    return [r.get("chunk", {}) for r in results]


def _team_of(chunk) -> str | None:
    meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
    return meta.get("team_id") or meta.get("team")


def _served_content(chunk) -> bool:
    """A chunk is 'served content' if it exposes real text, not a placeholder."""
    content = (chunk.get("content") or "") if isinstance(chunk, dict) else ""
    return bool(content) and "[PII_SCAN_UNAVAILABLE]" not in content


@pytest.mark.parametrize("row", params_for("L2"))
def test_l2(row):
    require_live(row.needs, row.owner)
    _, resp = perform(row)
    chunks = _chunks(resp)

    if row.variant == "HAPPY":
        assert chunks, "expected served facts for AA-OPS"
        assert all(c.get("pii_scanned") is True for c in chunks), \
            "only pii_scanned facts may be served"

    elif row.variant == "ADVERSARIAL":  # unscanned PII must not be served
        leaked = [c for c in chunks if c.get("pii_scanned") is False and _served_content(c)]
        assert not leaked, f"{row.expected} — leaked {len(leaked)} unscanned chunk(s)"

    elif row.variant == "ISOLATION":  # AA-CARGO must get zero AA-OPS rows
        foreign = [c for c in chunks if _team_of(c) not in (None, "AA-CARGO")]
        assert not foreign, f"{row.expected} — {len(foreign)} foreign row(s) leaked"

    elif row.variant == "FAILURE_INJECTION":  # quarantined content withheld
        assert not any(c.get("pii_scanned") is False and _served_content(c)
                       for c in chunks), row.expected
