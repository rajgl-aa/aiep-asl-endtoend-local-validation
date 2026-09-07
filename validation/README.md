# ASL cross-layer GA-validation suite (`validation/`)

A **behavioral** scenario matrix for the flight-disruption rebooking journey,
across every ASL layer (L1–L7).

## Purpose: behavioral, not liveness

`demo.py` (one directory up) proves *liveness*: "OK = the harness responded",
and it mocks exactly the governance/security controls that matter (see
`demo-run-final.log`: L7 `scan_proofs` all `SKIPPED`, sandbox `_mock:true`; L2
facts served as `[PII_SCAN_UNAVAILABLE]`; L6 dedup skipped yet approved).

This suite instead proves **behavior**: a test passes only when a control did
the *right thing* — blocked an injection, denied a cross-tenant read, failed
CLOSED when a dependency was down. Liveness is necessary but not sufficient for
GA; correct-control-behavior is the bar.

## The 4-variant matrix

Every layer gets four variants (`matrix.py`):

| Variant | What it sends | Control must… |
|---|---|---|
| `HAPPY` | legitimate AA rebooking | allow / serve |
| `ADVERSARIAL` | prompt-injection, competitor-airline query, or PII-exfiltration | fire (block / redact) |
| `ISOLATION` | AA-CARGO reaching for AA-OPS data / a foreign table | return nothing / 403 |
| `FAILURE_INJECTION` | PII scanner, policy engine, or DB down | fail **CLOSED** (deny / quarantine) |

## How to run

```bash
python -m pytest validation/ -q            # whole suite (mostly SKIPPED here)
python -m pytest validation/ -m adversarial
python -m pytest validation/ -m isolation
python -m pytest validation/ -m failure_injection
python -m pytest validation/test_l7.py -v  # one layer
```

## What "skipped" means

**A skip is NOT a pass.** Each skip carries the standard reason:

```
needs-live-env: <what is needed> | owner: <name>
```

It means the service/credential to run that behavioral assertion is absent in
this environment. This env has **no live L1–L7 services and no real credentials**
(no Azure PII scanner, no HiddenLayer, no Apigee bearer, no running services),
so almost everything skips. That is the correct, honest outcome — the suite
refuses to green-light anything it cannot actually verify.

Rows that encode a **known GA audit gap** (the deployed path does the wrong
thing today) are additionally marked `xfail(strict=False)`: run them against the
current ungoverned service and they record the gap as `xfailed` instead of a
hard failure, and flip to `xpassed` once the control is fixed.

## Scenario x layer x runnable-locally

"Runnable locally" = needs only a local service bring-up (no cloud creds).
Everything still skips in *this* env because no services are up.

| Layer (owner) | HAPPY | ADVERSARIAL | ISOLATION | FAILURE_INJECTION |
|---|---|---|---|---|
| L1 Sentinel/Axis/DB (Lok+Vijay) | needs Apigee key | needs Apigee key | needs DB + key · **gap: TABLE_ACL** | local |
| L2 Federated Gateway (Vijay) | local | local · pii-not-served | needs pg · **gap: RLS off** | local · quarantine |
| L3 Policy Engine (Vamsi) | local | local | local | local · **gap: fails OPEN** |
| L4 Agent SDK (Laxmi) | needs SDK | needs SDK | needs SDK + gw | needs SDK |
| L5 Orchestration (Vamsi+Lok+Laxmi) | needs orchestrator | needs orchestrator | needs orchestrator | needs orchestrator |
| L6 Registry/Reviewer (Niranjan+Pradeep) | local | needs sentinel · **gap: no injection detect** | local · **gap: no auth** | needs Azure Search · **gap: dedup** |
| L7 Tool Governance (Lakshmikanth+Lok) | local | needs sentinel · **gap: scans SKIPPED** | local | needs sandbox · **gap: _mock:true** |

`**gap:**` = documented audit finding encoded as an `xfail` expected-behavior
assertion (see each row's `audit_finding` in `matrix.py`).

## Encoded audit findings (expected-behavior assertions)

- **L7** — injection/exfiltration scans must NOT be `SKIPPED` in `scan_proofs`;
  sandbox output must not be `_mock:true`.
- **L3** — an unparseable policy condition must fail **CLOSED** (audit: fails open).
- **L2** — cross-tenant retrieve must return zero foreign rows; a fact with
  `pii_scanned=false` must never be served as content.
- **L6** — `/review-submission` must require auth; registry publish (dedup) must be gated.
- **L1** — a `layer_id` must not read a foreign table (TABLE_ACL wildcard gap).

## Honest status

With no live env, **almost everything skips — nothing here is green, and that is
correct.** Green requires an owner to do BOTH:

1. **Turn the control on** (the deployed path ships these controls OFF: L2 RLS,
   L3 fail-closed parsing, L6 auth + dedup gating, L7 scans + real sandbox,
   L1 table ACLs), and
2. **Supply the env** — start the layer's service and provide the credential
   named in the skip reason (`AA_SERVICES_KEY`, `AZURE_SEARCH_ENDPOINT`,
   `ASL_PROMPTSENTINEL_URL`, `ASL_SANDBOX_PROVIDER`, `ASL_ORCHESTRATOR_URL`, pg).

The suite is deliberately built so that a scaffold which honestly skips is the
success state; a scaffold that green-lights nothing real is the correct one.

## Files

- `conftest.py` — `Services` map, live-env detection, `require_live()` skip
  helper (standard reason format), the urllib HTTP helper, `perform()`,
  `params_for()` (marks rows), and the `live_env` fixture.
- `matrix.py` — the scenario matrix as data (`ScenarioRow` dataclass, 28 rows).
- `test_l1.py … test_l7.py` — per-layer parametrized behavioral tests.
- `pytest.ini` — marker registration + `addopts`.
