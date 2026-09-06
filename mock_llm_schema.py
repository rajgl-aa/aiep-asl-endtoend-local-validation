"""Schema-aware mock LLM for the Layer 6 reviewer agent (port 8766).

`asl dev start` (port 8765) answers plain prose, which cannot satisfy LangChain
structured-output calls (response_format=json_schema). This mock inspects the
request: when a json_schema response_format is present it synthesizes a valid
instance with type-driven defaults (enums -> first value); otherwise it returns
the same flight-flavoured canned completion as the dev proxy.

This is a HARNESS mock: generated content is placeholder text, not a real review.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


def _default_for(schema: dict):
    stype = schema.get("type")
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if stype == "string" or stype is None:
        return "demo-review-value"
    if stype == "number":
        return 0.5
    if stype == "integer":
        return 1
    if stype == "boolean":
        return False
    if stype == "array":
        return []
    if stype == "object":
        props = schema.get("properties", {})
        return {k: _default_for(v) for k, v in props.items()}
    return None


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        rf = (body.get("response_format") or {})
        schema = rf.get("json_schema", {}).get("schema")
        if rf.get("type") == "json_schema" and schema:
            content = json.dumps(_default_for(schema))
        else:
            msgs = body.get("messages") or []
            prompt = (msgs[-1].get("content") if msgs else "") or ""
            kw = ("flight", "travel", "seat", "reservation")
            if any(k in prompt.lower() for k in kw):
                content = ("Here is mock flight information: Flight AA123 departs DFW "
                           "at 08:00, arrives LAX at 10:30. [MOCK RESPONSE — schema mock]")
            else:
                content = ("This is a mock LLM response from the schema-aware local mock. "
                           "No real model was called.")
        resp = {
            "id": "mock-schema-001", "object": "chat.completion", "model": "local-mock",
            "created": 0,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        payload = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("schema-aware mock LLM on http://127.0.0.1:8766")
    HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
