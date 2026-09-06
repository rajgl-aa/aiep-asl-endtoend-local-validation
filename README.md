# Flight Disruption Assistant — ASL all-layer local demo

One airline scenario (passenger on cancelled AA100 DFW→LAX asks to be rebooked)
executed against **every ASL layer's harness running locally**. No AA VPN, no
Cloudsmith, no real LLM — the LLM hop is mocked.

## What each step proves

| Step | Layer | Harness demonstrated |
|---|---|---|
| Skill discovery | L3 | Skills Registry serves `rebook-passenger` invoke-spec (policy-validated registration) |
| Policy evaluation | L3 | Policy Engine `hv-laws` bundle: AA-related → `allow`, competitor query → `block` (law-004) |
| Tool invoke | L7 | `aa-agent-tools` 18-step pipeline: register → scan PASS → publish → invoke `fuel-burn-estimator` (B787-9) with policy decision + audit hash chain |
| Memory write | L2 | `aa-agent-data` SDK writes an LTM fact to local pgvector Postgres (quarantine note: without the Azure PII scanner, `pii_scanned=false`) |
| Federated retrieve | L2 | Gateway RRF-ranked retrieval with writer-agent provenance + retrieval trace id |
| L1 pipeline | L1 | Real `aa-agent-client`: Sentinel PII-mask → Model Axis route (`semi_intelligent`, cost estimate) → mock LLM → demask |
| Agent run | L4 | `aa-agent-sdk` `ChainOfThoughtAgent` with the **real L1 client injected** via the `llm_client` DI seam (`ASL_LOCAL_DEV=true`) |
| Manifest | L6 | `flight-disruption-assistant` manifest validated against `agent-manifest.schema.json` |
| Review | L6 | Marketplace Reviewer Agent returns a structured verdict (schema-aware mock LLM on :8766) |

## Service map (all localhost)

| Service | Port | Repo |
|---|---|---|
| Postgres (pgvector, Docker `asl-demo-pg`) | 5433 | docker |
| L1 ASL DB Gateway | 8001 | Layer1/aiep-asldb |
| L1 Model Axis | 8002 | Layer1/aiep-modelaxis |
| L1 Prompt Sentinel | 8003 | Layer1/aiep-promptsentinel |
| L3 Policy Engine | 8310 | Layer3/aiep-policyengine |
| L3 Skills Registry | 8311 | Layer3/aiep-skills-registry |
| L2 Federated Gateway | 8312 | Layer2/aiep-asl-federated-gateway |
| L7 Tool Governance | 8313 | Layer7/aa-agent-tools |
| L6 Marketplace Reviewer | 8314 | Layer6/aiep-marketplace-reviewer-agent |
| Mock LLM (`asl dev start`) | 8765 | Layer7/aiep-asl-cli |
| Schema-aware mock LLM (reviewer only) | 8766 | ./mock_llm_schema.py |

Note: the machine's own Postgres owns :5432 — the demo container maps 5433→5432.

## Run it

```bash
# 1. infra
docker start asl-demo-pg

# 2. services (each repo has its own venv from bring-up; see logs in repo .local-logs/ or logs/)
cd Layer1/aiep-asldb            && nohup pipenv run uvicorn app.main:app --port 8001 > /tmp/l1-asldb.log 2>&1 &
cd Layer1/aiep-modelaxis        && nohup pipenv run uvicorn app.main:app --port 8002 > /tmp/l1-axis.log 2>&1 &
cd Layer1/aiep-promptsentinel   && nohup pipenv run uvicorn app.main:app --port 8003 > /tmp/l1-ps.log 2>&1 &
cd Layer3/aiep-policyengine     && nohup env ENV=local PYTHONPATH=stubs pipenv run uvicorn app.main:app --port 8310 > /tmp/l3-pe.log 2>&1 &
cd Layer3/aiep-skills-registry  && nohup env ENV=local pipenv run uvicorn app.main:app --port 8311 > /tmp/l3-skills.log 2>&1 &
cd Layer2/aiep-asl-federated-gateway && nohup bash -c 'set -a && . ./.env && set +a && .venv-demo/bin/python -m uvicorn app.main:app --port 8312' > /tmp/l2-gw.log 2>&1 &
cd Layer7/aa-agent-tools        && nohup bash -c 'set -a && . ./.env && set +a && .venv-demo/bin/python -m uvicorn app.main:app --port 8313' > /tmp/l7-tools.log 2>&1 &
cd Layer6/aiep-marketplace-reviewer-agent && nohup .venv/bin/python -m uvicorn app.main:app --port 8314 --host 127.0.0.1 > /tmp/l6-reviewer.log 2>&1 &
# dev proxy (from this directory, where policy.yaml lives):
nohup ../Layer7/aiep-asl-cli/asl-cli/.venv-demo/bin/asl dev start --policy policy.yaml --port 8765 > dev-proxy.log 2>&1 &
nohup .venv/bin/python mock_llm_schema.py > mock-schema.log 2>&1 &

# 3. the demo
cd demo-airline-agent && .venv/bin/python demo.py
```

`demo.py` is defensive: a layer that is down prints `⛔ DOWN — <reason>` and the run continues.

## Files

- `demo.py` — the orchestrated all-layer demo (scenario, banners, summary)
- `mock_llm_schema.py` — schema-aware mock for the L6 reviewer (structured-output calls)
- `policy.yaml` — dev-proxy policy (block competitor airlines, rephrase refunds)
- `demo-run-final.log` — captured all-green run

## Honest limits

- The LLM is mocked: answers are canned. Swap `AA_APIM_URL` to real APIM for real completions.
- L2 quarantine: facts written without the Azure PII scanner are stored but not served (`pii_scanned=false`) — the retrieve step reads facts previously marked scanned.
- Reviewer verdicts are placeholder content from the schema mock — the harness (orchestration → structured decision → fallback) is what's being shown.
