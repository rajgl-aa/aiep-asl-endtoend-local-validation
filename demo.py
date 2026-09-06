"""Flight Disruption Assistant — every-ASL-layer local harness demo.

One airline scenario, one run, every layer engaged:

  Passenger: "My flight AA100 DFW->LAX was cancelled. I'm Jane Doe, record locator
  ABC123, jane.doe@example.com, AAdvantage 987654321. Rebook me."

  L3  Skills Registry  -> discover the rebook-passenger skill invoke-spec
  L3  Policy Engine    -> evaluate the passenger message (allow) + competitor query (block)
  L7  Tool Governance  -> invoke fuel-burn-estimator through the 18-step pipeline
  L2  Federated Memory -> write the disruption fact to LTM, retrieve it semantically
  L1  Sentinel+Axis    -> PII mask, model route, mock-LLM completion, demask (via aa-agent-client)
  L4  Agent SDK        -> ChainOfThoughtAgent with the REAL L1 client injected
  L6  Registry/Review  -> validate manifest against schema, submit to reviewer agent

Everything is defensive: a layer that is down is reported DOWN with the reason and
the demo continues, so partial stacks still demo.

Run:  .venv/bin/python demo.py            (from this directory)
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
import urllib.request
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Service map (all local). Adjust here if your bring-up used different ports.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Services:
    asldb: str = "http://localhost:8001"        # L1 ASL DB Gateway
    modelaxis: str = "http://localhost:8002"    # L1 Model Axis
    sentinel: str = "http://localhost:8003"     # L1 Prompt Sentinel
    policy: str = "http://localhost:8310"       # L3 Policy Engine
    skills: str = "http://localhost:8311"       # L3 Skills Registry
    gateway: str = "http://localhost:8312"      # L2 Federated Retrieval Gateway
    tools: str = "http://localhost:8313"        # L7 aa-agent-tools server
    reviewer: str = "http://localhost:8314"     # L6 Marketplace Reviewer Agent
    mock_llm: str = "http://127.0.0.1:8765"     # L7 `asl dev start` mock LLM proxy


S = Services()

PASSENGER_MSG = (
    "My flight AA100 from DFW to LAX tomorrow was cancelled. I'm Jane Doe, "
    "record locator ABC123, email jane.doe@example.com, AAdvantage 987654321. "
    "Please rebook me on the next available flight and trace my checked bag."
)

# L1 client environment: real SDK pointed at local Sentinel/Axis/mock-LLM.
os.environ.setdefault("AA_APIM_URL", S.mock_llm)
os.environ.setdefault("AA_APIM_KEY", "dummy-local-demo-key")
os.environ.setdefault("AA_MODEL_AXIS_URL", S.modelaxis)
os.environ.setdefault("AA_SENTINEL_URL", S.sentinel)
os.environ.setdefault("ASL_LOCAL_DEV", "true")   # L4 SDK: NoOp HiddenLayer etc.
os.environ.setdefault("ENV", "local")

RESULTS: list[tuple[str, str]] = []


# ---------------------------------------------------------------------------
def banner(layer: str, title: str) -> None:
    print(f"\n{'=' * 74}\n  {layer}  |  {title}\n{'=' * 74}")


def record(layer: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((layer, "OK  " if ok else "DOWN"))
    mark = "✅" if ok else "⛔"
    print(f"{mark} {layer}: {'OK' if ok else 'DOWN — ' + detail}")


def show(label: str, payload, limit: int = 700) -> None:
    try:
        text = json.dumps(payload, indent=2, default=str)
    except TypeError:
        text = str(payload)
    if len(text) > limit:
        text = text[:limit] + " …(truncated)"
    print(textwrap.indent(text, "    "), f"\n    ^ {label}\n")


def http(method: str, url: str, body: dict | None = None, timeout: float = 8.0,
         headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode() or "{}"
        return resp.status, json.loads(raw)


def probe(url: str) -> bool:
    for path in ("/api/v1/status", "/health", "/docs", "/"):
        try:
            http("GET", url + path, timeout=2.0)
            return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# L3 — Skills Registry: discover the rebook skill
# ---------------------------------------------------------------------------
def l3_skills() -> dict | None:
    banner("L3", "Skills Registry — discover 'rebook-passenger' invoke-spec")
    try:
        _, skills = http("GET", f"{S.skills}/api/v1/skills")
        rows = skills if isinstance(skills, list) else skills.get("skills", [])
        names = [s.get("name") for s in rows]
        show("registered skills", names)
        skill_id = next((s.get("id") or s.get("skill_id") or s.get("name")
                         for s in rows
                         if "rebook" in json.dumps(s).lower()), None)
        if not skill_id:
            raise RuntimeError(f"no rebook skill found in {names}")
        _, spec = http("GET", f"{S.skills}/api/v1/skills/{skill_id}/invoke-spec")
        show(f"invoke-spec: {skill_id}", spec)
        record("L3 Skills Registry", True)
        return spec
    except Exception as exc:
        record("L3 Skills Registry", False, str(exc)[:160])
        return None


# ---------------------------------------------------------------------------
# L3 — Policy Engine: allow passenger msg, block competitor query
# ---------------------------------------------------------------------------
def l3_policy() -> None:
    banner("L3", "Policy Engine — evaluate passenger message (expect allow)")
    try:
        _, ver = http("GET", f"{S.policy}/api/v1/policies/version", timeout=30.0)
        show("policy bundle version", ver)
        for label, ctx in (
            ("passenger rebooking request (AA-related)", {"input": {"is_aa_related": True}}),
            ("competitor-airline query (expect BLOCK)", {"input": {"is_aa_related": False}}),
        ):
            _, ev = http("POST", f"{S.policy}/api/v1/policies/evaluate",
                         {"surface": "input", "context": ctx}, timeout=30.0)
            show(f"evaluate: {label}", ev)
        record("L3 Policy Engine", True)
    except Exception as exc:
        record("L3 Policy Engine", False, str(exc)[:160])


# ---------------------------------------------------------------------------
# L7 — Tool Governance: fuel-burn-estimator through the invoke pipeline
# ---------------------------------------------------------------------------
TOOLS_AUTH = {"Authorization": "Bearer dev-noop"}  # LocalDevAuthProvider (local only)


def l7_tools() -> None:
    banner("L7", "aa-agent-tools — fuel-burn-estimator via governance pipeline")
    try:
        _, tools = http("GET", f"{S.tools}/api/v1/tools?namespace=crewops",
                        headers=TOOLS_AUTH)
        show("registered tools (crewops)", [t["name"] for t in tools.get("tools", [])])
        tool_id = next(t["tool_id"] for t in tools.get("tools", [])
                       if t["name"] == "fuel-burn-estimator")
        _, resp = http("POST", f"{S.tools}/api/v1/tools/{tool_id}/invoke", {
            "input": {"aircraft_type": "B787-9", "distance_nm": 1235, "payload_kg": 42000},
        }, headers=TOOLS_AUTH)
        show("fuel-burn-estimator invoke (policy+audit)", resp)
        record("L7 Tool Governance", True)
    except Exception as exc:
        record("L7 Tool Governance", False, str(exc)[:160])


# ---------------------------------------------------------------------------
# L2 — Federated memory: SDK LTM write + gateway retrieval with RRF ranking
# ---------------------------------------------------------------------------
def l2_memory() -> None:
    banner("L2", "Federated retrieval — SDK LTM write, gateway semantic recall")
    fact_id = None
    try:
        import asyncio
        import aa_agent_data

        async def _write() -> str:
            await aa_agent_data.configure(
                db_host="localhost", db_port=5433, db_name="asl_l2_data",
                db_user="asl_l2_app", db_password="postgres", db_ssl="disable",
            )
            try:
                fact = await aa_agent_data.ltm.write(
                    key="disruption_aa100_dfw_lax_2026_09_07",
                    value=("Passenger Jane Doe (record locator ABC123) on cancelled flight "
                           "AA100 DFW-LAX accepted rebooking to AA1288 departing 18:40."),
                    team_id="AA-OPS",
                    agent_id="flight-disruption-assistant",
                    metadata={"source": "disruption_desk", "flight": "AA100"},
                )
                return fact.fact_id
            finally:
                await aa_agent_data.close()

        fact_id = asyncio.run(_write())
        show("LTM write via aa-agent-data SDK", {"fact_id": fact_id,
                                                 "note": "row lands quarantined "
                                                         "(pii_scanned=false) without the "
                                                         "Azure PII scanner — fail-safe"})
        record("L2 Memory write (SDK)", True)
    except Exception as exc:
        record("L2 Memory write (SDK)", False, str(exc)[:160])
    try:
        _, r = http("POST", f"{S.gateway}/api/v1/retrieve/", {
            "query": "flight delayed overnight hotel rebooking",
            "team_id": "AA-OPS",
            "agent_id": "aa-offers-agent",
            "top_k": 5,
        })
        show("federated retrieve (RRF + provenance)", r)
        record("L2 Federated retrieve", True)
    except Exception as exc:
        record("L2 Federated retrieve", False, str(exc)[:160])


# ---------------------------------------------------------------------------
# L1 — Full pipeline via the real aa-agent-client: mask → route → mock LLM
# ---------------------------------------------------------------------------
def l1_pipeline() -> None:
    banner("L1", "Sentinel → Model Axis → mock LLM → demask (aa-agent-client)")
    try:
        from aa_agent_client import LLMClient  # real L1 SDK
    except ImportError as exc:
        record("L1 Pipeline (aa-agent-client)", False, f"SDK not importable: {exc}")
        return
    try:
        with LLMClient(agent_id="flight-disruption-assistant") as client:
            result = client.complete(
                system_prompt="You are an American Airlines disruption rebooking assistant.",
                user_prompt=PASSENGER_MSG,
                task_type="qa",
                strategy="semi_intelligent",
                team_id="AA-OPS",
                agent_id="flight-disruption-assistant",
                allowed_models=["gpt-5-nano", "gpt-5-mini", "gpt-4.1-mini", "gpt-5.6-sol", "gpt-5"],
            )
        show("LLMClient.complete() — text (demasked)",
             getattr(result, "text", result))
        show("routing + usage",
             {k: getattr(result, k, None)
              for k in ("model_used", "deployment_name", "provider", "cost_usd")})
        record("L1 Pipeline (aa-agent-client)", True)
    except Exception as exc:
        record("L1 Pipeline (aa-agent-client)", False, str(exc)[:200])


# ---------------------------------------------------------------------------
# L4 — Agent SDK: ChainOfThoughtAgent with the REAL L1 client injected
# ---------------------------------------------------------------------------
def l4_agent() -> None:
    banner("L4", "aa-agent-sdk — ChainOfThoughtAgent w/ real L1 client (DI seam)")
    try:
        import asyncio
        from aa_agent_sdk.manifest import (AgentManifest, LLMConfig,
                                           MemoryConfig, ReasoningConfig)
        from aa_agent_sdk.models import AgentInput
        from aa_agent_sdk.agents.cot import ChainOfThoughtAgent
        from aa_agent_client import LLMClient
    except ImportError as exc:
        record("L4 Agent SDK", False, f"SDKs not importable: {exc}")
        return
    try:
        manifest = AgentManifest(
            agent_id="flight-disruption-assistant",
            team_id="AA-OPS",
            agent_version="1.0.0-demo",
            system_prompt=("You are an American Airlines disruption rebooking assistant. "
                           "Confirm rebookings concisely and never reveal passenger PII."),
            reasoning=ReasoningConfig(pattern="cot"),
            llm=LLMConfig(model="gpt-5", strategy="semi_intelligent"),
            # L4 allows only [llm.model] — must sit at the CoT task's complexity tier
            memory=MemoryConfig(),
        )
        client = LLMClient(agent_id="flight-disruption-assistant")
        agent = ChainOfThoughtAgent(manifest, llm_client=client)

        async def _run():
            return await agent.ainvoke(AgentInput(
                session_id="demo-disruption-001",
                user_message=("Passenger on cancelled AA100 DFW-LAX, record locator ABC123. "
                              "Draft a one-paragraph rebooking confirmation."),
            ))

        result = asyncio.run(_run())
        status = getattr(result, "status", None)
        output = getattr(result, "output", result)
        show("ChainOfThoughtAgent.ainvoke()", {"status": status, "output": output})
        if status not in ("completed", "success") or not output:
            raise RuntimeError(f"agent run ended with status={status!r}")
        record("L4 Agent SDK", True)
    except Exception as exc:
        record("L4 Agent SDK", False, str(exc)[:200])


# ---------------------------------------------------------------------------
# L6 — Registry manifest validation + reviewer agent submission
# ---------------------------------------------------------------------------
def l6_registry() -> None:
    banner("L6", "Agent Registry + Marketplace Reviewer")
    manifest_path = os.path.join(
        os.path.dirname(__file__), "..", "Layer6", "aiep-agent-registry",
        "agents", "flight-disruption-assistant", "manifest.json",
    )
    manifest_path = os.path.abspath(manifest_path)
    try:
        schema = json.load(open(os.path.join(
            os.path.dirname(manifest_path), "..", "..",
            "schemas", "agent-manifest.schema.json")))
        manifest = json.load(open(manifest_path))
        try:
            import jsonschema
            jsonschema.validate(manifest, schema)
            show("manifest schema validation", {"manifest": manifest.get("name"), "valid": True})
        except ImportError:
            show("manifest schema validation", {"manifest": manifest.get("name"),
                                                "note": "jsonschema not installed, skipped"})
        record("L6 Registry (manifest)", True)
    except Exception as exc:
        record("L6 Registry (manifest)", False, str(exc)[:160])
    try:
        _, r = http("POST", f"{S.reviewer}/api/v1/review-submission",
                    {"github_url": "https://github.com/American-Airlines/flight-disruption-assistant",
                     "manifest": manifest if 'manifest' in dir() else {}}, timeout=60.0)
        show("reviewer verdict", r)
        record("L6 Reviewer Agent", True)
    except Exception as exc:
        record("L6 Reviewer Agent", False, str(exc)[:160])


# ---------------------------------------------------------------------------
def main() -> None:
    print("Flight Disruption Assistant — ASL all-layer local harness demo")
    print("Services:", json.dumps(S.__dict__, indent=2))
    l3_skills()
    l3_policy()
    l7_tools()
    l2_memory()
    l1_pipeline()
    l4_agent()
    l6_registry()
    banner("SUMMARY", "")
    for layer, status in RESULTS:
        print(f"  {status}  {layer}")
    print()


if __name__ == "__main__":
    main()
