#!/usr/bin/env bash
# t2_shim_gate.sh — T2 validation gate: run the frozen 20-case shim battery against a
# LIVE served model and verify UniformToolShim extraction is 20/20.
#
# This is the acceptance gate the staging harness was missing (M21). It exercises the
# actual tool-call extraction layer (serving/tool_call_shim.py, guided-JSON) end-to-end
# against the served endpoint — NOT a smoke test, the real shim path.
#
# Usage:  bash tools/t2_shim_gate.sh <model_key> [port]
#   model_key: qwen3-32b | qwen3-8b | qwen3-30b-a3b | gemma4-31b
#   port: default 8000 (serving) — staging uses the PORT it launched on
# Requires: the model already served (serve_*.sh or staging_collect.sh), HF deps in env.
# Output: evidence/t2_shim_<key>_<ts>.json + a one-line verdict. Exit 0 iff 20/20.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${1:?usage: t2_shim_gate.sh <model_key> [port]}"
PORT="${2:-8000}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="evidence/t2_shim_${KEY}_${TS}.json"
mkdir -p evidence
python3 - "$KEY" "$PORT" "$OUT" << 'PYEOF'
import sys, json, urllib.request
key, port, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, "serving")
from tool_call_shim import UniformToolShim, TOOL_CALL_SCHEMA

battery = json.load(open("smoke/shim_probe_20.json"))
tools = battery["tools_common"]

class LiveClient:
    """Minimal OpenAI-compatible chat.completions client over urllib (no openai pkg needed)."""
    def __init__(self, port): self.url = f"http://localhost:{port}/v1/chat/completions"
    class _NS:  # tiny namespace mimicking openai response objects
        def __init__(self, d): self.__dict__.update(d)
    class chat:
        class completions:
            @staticmethod
            def create(model, messages, extra_body=None, temperature=0.0, _self=None):
                # bound at runtime below
                raise NotImplementedError
    def chat_completions_create(self, model, messages, extra_body=None, temperature=0.0):
        payload = {"model": model, "messages": messages, "temperature": temperature,
                   "max_tokens": 512}
        if extra_body: payload.update(extra_body)
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
        msg = d["choices"][0]["message"]
        usage = d.get("usage", {})
        class Resp: pass
        resp = Resp()
        resp.choices = [type("C", (), {"message": type("M", (), {"content": msg.get("content","")})()})()]
        resp.usage = type("U", (), {"model_dump": lambda s: usage})()
        return resp

client = LiveClient(port)
# attach the create method UniformToolShim expects
client.chat = type("X", (), {})()
client.chat.completions = type("Y", (), {})()
client.chat.completions.create = client.chat_completions_create

shim = UniformToolShim(client, model_name=key)
results = []
npass = 0
for case in battery["cases"]:
    exp = case["expect"]
    resp = shim.generate(case["messages"], tools)
    action = resp["action"]
    shim_fail = action.get("content") == "[shim_failure]"
    ok_type = action.get("type") == exp["action_type"]
    ok = ok_type and not shim_fail
    if exp["action_type"] == "tool_call" and not shim_fail:
        ok = ok and action.get("tool") == exp.get("tool")
        req = exp.get("required_args", [])
        ok = ok and all(k in (action.get("args") or {}) for k in req)
    results.append({"id": case["id"], "pass": ok, "shim_failure": shim_fail,
                    "got_type": action.get("type"), "want_type": exp["action_type"],
                    "got_tool": action.get("tool"), "want_tool": exp.get("tool")})
    npass += ok
verdict = f"T2 {key}: {npass}/{len(battery['cases'])} {'PASS' if npass==len(battery['cases']) else 'FAIL'}"
json.dump({"model": key, "ts": out, "pass": npass, "total": len(battery["cases"]),
           "verdict": verdict, "cases": results}, open(out, "w"), indent=2)
print(verdict)
print("artifact:", out)
sys.exit(0 if npass == len(battery["cases"]) else 1)
PYEOF
