"""Import a Layer 6 agent-registry manifest into aiep-agent-builder as a canvas graph.

Turns the text manifest (what CI validates / what the registry hosts) into the
builder's graph JSON (what the canvas renders) via the builder's public API —
the same endpoint the canvas itself uses. This is the bridge that lets the
canvas *visualize* agents that were created elsewhere (CLI scaffold / registry),
instead of requiring them to be drawn by hand.

Usage:
    .venv/bin/python import_manifest_to_builder.py [manifest.json] [--builder http://localhost:8100]
"""

from __future__ import annotations

import json
import sys
import urllib.request

BUILDER = "http://localhost:8100"


def node(nid: str, ntype: str, x: int, y: int, data: dict) -> dict:
    return {"id": nid, "type": ntype, "position": {"x": x, "y": y}, "data": data}


def edge(eid: str, src: str, dst: str, kind: str, label: str = "") -> dict:
    return {"id": eid, "source": src, "target": dst, "kind": kind, "label": label}


def agent_node(nid: str, name: str, x: int, y: int, desc: str, is_root: bool = False) -> dict:
    return node(nid, "agent", x, y, {
        "name": name, "description": desc, "model": "gpt-4o",
        "instructions": desc, "is_root": is_root, "memory": True,
        "output_config": {},
    })


def build_graph(manifest: dict) -> dict:
    name = manifest["name"]
    caps = manifest.get("capabilities", [])
    nodes, edges = [], []
    y = 80

    nodes.append(node("input", "chat-input", 0, 200, {
        "name": "Passenger Request",
        "input_schema": manifest.get("input_schema", {}),
    }))

    nodes.append(agent_node("root", name, 320, 200,
                            manifest.get("description", ""), is_root=True))
    edges.append(edge("e-input", "input", "root", "flow", "passenger message"))

    # capabilities -> delegated sub-agents
    cap_names = {
        "flight-disruption": "Flight Operations Agent",
        "passenger-rebooking": "Rebooking Agent",
        "baggage-tracing": "Baggage Agent",
        "customer-notification": "Notification Agent",
    }
    sub_ids = []
    for i, cap in enumerate(caps):
        sid = f"sub-{i}"
        sub_ids.append(sid)
        nodes.append(agent_node(sid, cap_names.get(cap, cap.replace("-", " ").title()),
                                640, y + i * 170, f"Handles: {cap}"))
        edges.append(edge(f"e-{sid}", "root", sid, "delegation", cap))

    # tools / knowledge / memory (builder catalog node types)
    n_tools = len(caps)
    nodes.append(node("mem", "session-memory", 640, y + n_tools * 170,
                      {"name": "Session Memory", "scope": "thread"}))
    edges.append(edge("e-mem", "root", "mem", "tool", "conversation context"))

    nodes.append(node("kb", "rag", 960, 80, {
        "name": "Disruption Policies KB",
        "description": "IROPS/rebooking policy knowledge base",
    }))
    nodes.append(node("api", "rest-api", 960, 280, {
        "name": "Rebooking API",
        "endpoint": manifest.get("endpoint_url", ""),
        "description": "Commit rebooking to PNR",
    }))
    edges.append(edge("e-kb", sub_ids[0] if sub_ids else "root", "kb", "tool", "policy lookup"))
    edges.append(edge("e-api", sub_ids[1] if len(sub_ids) > 1 else "root", "api", "tool", "commit"))

    # governance, straight from manifest fields
    gov = []
    if manifest.get("hitl_required"):
        gov.append(("hitl", "human-approval", "HITL before PNR commit"))
    if manifest.get("pii_risk") in ("high", "medium") or manifest.get("data_classification"):
        gov.append(("policy", "policy", f"policy · {manifest.get('data_classification', '')} · pii={manifest.get('pii_risk')}"))
    gov.append(("egress", "egress-control", "egress allowlist"))
    gov.append(("audit", "audit-logging", "audit trail"))
    for i, (gid, gtype, glabel) in enumerate(gov):
        nodes.append(node(gid, gtype, 320 + i * 220, 620, {"name": glabel}))
        edges.append(edge(f"e-{gid}", "root", gid, "governance", gtype))

    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}


def post(base: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read() or b"{}")


def main() -> None:
    manifest_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else \
        "../Layer6/aiep-agent-registry/agents/flight-disruption-assistant/manifest.json"
    builder = BUILDER
    if "--builder" in sys.argv:
        builder = sys.argv[sys.argv.index("--builder") + 1]

    manifest = json.load(open(manifest_path))
    body = {
        "name": f"{manifest['name']} (imported from registry manifest)",
        "description": manifest.get("description", ""),
        "environment": "local",
        "graph": build_graph(manifest),
    }
    created = post(builder, "/api/v1/systems", body)
    sys_id = created.get("id") or created.get("system_id")
    print(f"created system {sys_id}: {body['name']} "
          f"({len(body['graph']['nodes'])} nodes, {len(body['graph']['edges'])} edges)")
    print(f"view on canvas: http://localhost:3000")


if __name__ == "__main__":
    main()
