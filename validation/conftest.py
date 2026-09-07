"""Shared fixtures + honest live-env detection for the ASL GA-validation suite.

This suite is BEHAVIORAL, not liveness: a test passes only when a governance
control did the right thing. With no live services and no real credentials in
this environment, almost everything SKIPS with the standard reason:

    needs-live-env: <what is needed> | owner: <name>

A skip is NOT a pass. Green requires an owner to (a) turn the control on and
(b) supply the service/credential. Nothing here fabricates a passing result.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import pytest

import matrix


# ---------------------------------------------------------------------------
# Service map — mirrors demo.py exactly (all local).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Services:
    asldb: str = "http://localhost:8001"      # L1 ASL DB Gateway
    modelaxis: str = "http://localhost:8002"  # L1 Model Axis
    sentinel: str = "http://localhost:8003"   # L1 Prompt Sentinel
    policy: str = "http://localhost:8310"     # L3 Policy Engine
    skills: str = "http://localhost:8311"     # L3 Skills Registry
    gateway: str = "http://localhost:8312"    # L2 Federated Retrieval Gateway
    tools: str = "http://localhost:8313"      # L7 aa-agent-tools server
    reviewer: str = "http://localhost:8314"   # L6 Marketplace Reviewer Agent
    mock_llm: str = "http://127.0.0.1:8765"   # L7 `asl dev start` mock LLM proxy


S = Services()

# Logical service name -> local TCP port (used for reachability detection).
SERVICE_PORTS: dict[str, int] = {
    "asldb": 8001,
    "modelaxis": 8002,
    "sentinel": 8003,
    "policy": 8310,
    "skills": 8311,
    "gateway": 8312,
    "tools": 8313,
    "reviewer": 8314,
    "mock_llm": 8765,
}

# Credentials / config that gate a REAL governance control (cloud-backed).
KNOWN_CREDS: dict[str, str] = {
    "AA_SERVICES_KEY": "Apigee bearer for Model Axis + Prompt Sentinel (else 401)",
    "AZURE_SEARCH_ENDPOINT": "Azure AI Search — L6 dedup + L2 vector",
    "ASL_PROMPTSENTINEL_URL": "wired Prompt Sentinel URL so L7 scans actually run",
    "ASL_SANDBOX_PROVIDER": "real sandbox provider so L7 output is not _mock:true",
    "ASL_ORCHESTRATOR_URL": "L5 saga/orchestration engine endpoint",
}


# ---------------------------------------------------------------------------
# Tiny HTTP helper — reuses demo.py's urllib pattern, but returns the status
# code even on 4xx/5xx so tests can assert fail-CLOSED (401/403/5xx) behavior.
# ---------------------------------------------------------------------------
def _loads(raw: str):
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"_raw": raw}


def http(method: str, url: str, body: dict | None = None, timeout: float = 8.0,
         headers: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, _loads(exc.read().decode())


def perform(row) -> tuple[int, object]:
    """Execute a matrix row's declared HTTP call (service/method/path/body)."""
    base = getattr(S, row.service)
    return http(row.method, base + row.path, row.body or None,
                headers=row.headers or None)


# ---------------------------------------------------------------------------
# Live-env detection.
# ---------------------------------------------------------------------------
def _port_open(port: int, host: str = "localhost", timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _import_available(module: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _present(req: str) -> bool:
    """Is a single requirement satisfied right now?"""
    if req.startswith("import:"):
        return _import_available(req.split(":", 1)[1])
    if req.startswith("pg:"):
        return _port_open(int(req.split(":", 1)[1]))
    if req in SERVICE_PORTS:
        return _port_open(SERVICE_PORTS[req])
    if req in KNOWN_CREDS or req.isupper():
        return bool(os.environ.get(req))
    return False  # unknown token (e.g. an orchestrator that does not exist here)


def _describe(req: str) -> str:
    if req.startswith("import:"):
        return f"python package '{req.split(':', 1)[1]}' not importable"
    if req.startswith("pg:"):
        return f"postgres on port {req.split(':', 1)[1]} not reachable"
    if req in SERVICE_PORTS:
        return f"service '{req}' (port {SERVICE_PORTS[req]}) not reachable"
    if req in KNOWN_CREDS:
        return f"{req} unset ({KNOWN_CREDS[req]})"
    if req.isupper():
        return f"env var {req} unset"
    return f"'{req}' unavailable"


def require_live(service_or_cred, owner: str) -> None:
    """Skip with the standard reason unless every requirement is present.

    `service_or_cred` is a single token or an iterable of tokens. Tokens:
      - a service name (port reachability): 'gateway', 'policy', ...
      - a credential env var: 'AA_SERVICES_KEY', 'AZURE_SEARCH_ENDPOINT', ...
      - 'import:<module>' (SDK importable), 'pg:<port>' (postgres reachable)
    """
    reqs = [service_or_cred] if isinstance(service_or_cred, str) else list(service_or_cred)
    missing = [r for r in reqs if not _present(r)]
    if missing:
        pytest.skip("needs-live-env: "
                    + "; ".join(_describe(m) for m in missing)
                    + f" | owner: {owner}")


# ---------------------------------------------------------------------------
# Fixtures + parametrization.
# ---------------------------------------------------------------------------
@dataclass
class LiveEnv:
    services: dict[str, bool] = field(default_factory=dict)
    creds: dict[str, bool] = field(default_factory=dict)

    def require(self, service_or_cred, owner: str) -> None:
        require_live(service_or_cred, owner)


@pytest.fixture
def live_env() -> LiveEnv:
    """Snapshot of what is reachable/present (for reporting + convenience)."""
    return LiveEnv(
        services={n: _port_open(p) for n, p in SERVICE_PORTS.items()},
        creds={c: bool(os.environ.get(c)) for c in KNOWN_CREDS},
    )


_VARIANT_MARK = {
    "ADVERSARIAL": "adversarial",
    "ISOLATION": "isolation",
    "FAILURE_INJECTION": "failure_injection",
}


def params_for(layer: str) -> list:
    """Build parametrize params for a layer, attaching markers per row.

    - not runnable locally  -> `needs_live_env` marker
    - variant               -> `adversarial` / `isolation` / `failure_injection`
    - documented GA gap      -> `xfail(strict=False)` so running against the
      current (ungoverned) deployed path records the gap instead of a hard fail.
    """
    params = []
    for row in matrix.rows_for(layer):
        marks = []
        if not row.runnable_locally:
            marks.append(pytest.mark.needs_live_env)
        if row.variant in _VARIANT_MARK:
            marks.append(getattr(pytest.mark, _VARIANT_MARK[row.variant]))
        if row.expected_gap:
            marks.append(pytest.mark.xfail(reason=row.audit_finding, strict=False))
        params.append(pytest.param(row, id=row.id, marks=marks))
    return params


def pytest_configure(config) -> None:
    for name, desc in (
        ("needs_live_env", "requires a live service/credential absent in this env"),
        ("adversarial", "negative / injection / off-policy / exfiltration case"),
        ("isolation", "cross-tenant / cross-layer isolation case"),
        ("failure_injection", "dependency-down; asserts fail-closed vs fail-open"),
    ):
        config.addinivalue_line("markers", f"{name}: {desc}")
