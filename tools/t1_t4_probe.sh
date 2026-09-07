#!/usr/bin/env bash
# t1_t4_probe.sh — combined T1 (needle-in-context retrieval) + T4 (throughput) probe.
#
# T1: place a unique fact ("needle") deep inside a ~15.5k-token filler context and ask
#     for it — validates retrieval at the pilot's working context length (frozen 16384).
# T4: time that long episode + one short smoke; derive decode tokens/s at pilot settings
#     (temperature 0, shim path not used here — this measures raw serving throughput).
# One live model gives BOTH metrics in one launch (user-delegated decision 2026-09-07,
# R0: halve launches/GPU-hours; the two metrics are independent — correctness vs timing).
#
# Usage:  bash tools/t1_t4_probe.sh <model_key> [port]
# Requires: model already served (serve_*.sh), port default 8000.
# Output: evidence/t1_t4_<key>_<ts>.json + one-line verdict. Exit 0 iff needle retrieved.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${1:?usage: t1_t4_probe.sh <model_key> [port]}"
PORT="${2:-8000}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="evidence/t1_t4_${KEY}_${TS}.json"
mkdir -p evidence
python3 - "$KEY" "$PORT" "$OUT" << 'PYEOF'
import sys, json, time, urllib.request
key, port, out = sys.argv[1], sys.argv[2], sys.argv[3]

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # bypass proxy env

def served_name():
    req = urllib.request.Request(f"http://localhost:{port}/v1/models")
    with opener.open(req, timeout=30) as r:
        ids = [m["id"] for m in json.loads(r.read().decode())["data"]]
    if key in ids: return key
    if len(ids) == 1: return ids[0]
    print(f"STOP: gate key '{key}' not among served models {ids}"); sys.exit(2)

def chat(model, messages, max_tokens):
    payload = {"model": model, "messages": messages, "temperature": 0.0,
               "max_tokens": max_tokens}
    req = urllib.request.Request(f"http://localhost:{port}/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with opener.open(req, timeout=600) as r:
        d = json.loads(r.read().decode())
    dt = time.time() - t0
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content") or "", "reasoning": msg.get("reasoning") or "",
            "usage": d.get("usage", {}), "seconds": round(dt, 2)}

name = served_name()
result = {"model": key, "served_name": name, "ts": out}

# ---------- T4a: short smoke (baseline latency, warms the path) ----------
smoke = chat(name, [{"role": "user", "content": "Reply with exactly: OK"}], 8)
result["smoke"] = smoke

# ---------- T1 + T4b: needle episode (~15.5k tokens), timed ----------
NEEDLE = ("The pilot's locked retrieval code is KX-7429-ZEBRA. "
          "This code appears nowhere else in this document.")
FILLER_SENT = ("This is filler sentence number %d of the context document, "
               "written to occupy space without carrying any signal. ")

def build(n_sent):
    """Filler of n_sent sentences with the needle at ~80% depth."""
    pos = int(n_sent * 0.80)
    parts = []
    for i in range(n_sent):
        parts.append(FILLER_SENT % i)
        if i == pos:
            parts.append("\n" + NEEDLE + "\n")
    context = "".join(parts)
    return ("Read the document below, then answer the question with the code only.\n\n"
            "DOCUMENT:\n" + context +
            "\n\nQUESTION: What is the pilot's locked retrieval code?")

# Repetitive filler compresses unpredictably under BPE, so don't trust char math (M15):
# run a 200-sentence calibration call, read the server's OWN prompt_tokens, then scale
# to land at ~15.5k. ctx is frozen 16384; reserve ~800 for needle+question+generation.
TARGET_PROMPT_TOK = 15500
calib = chat(name, [{"role": "user", "content": build(200)}], 64)
calib_tok = calib.get("usage", {}).get("prompt_tokens", 0)
if calib_tok <= 0:
    print("STOP: calibration call returned no prompt_tokens — cannot size the needle episode")
    sys.exit(2)
n_sent = max(50, int(200 * TARGET_PROMPT_TOK / calib_tok))
prompt = build(n_sent)

needle = chat(name, [{"role": "user", "content": prompt}], 64)
result["calibration"] = {"calib_prompt_tokens": calib_tok, "n_sent_used": n_sent}
result["needle"] = needle
result["needle_found"] = "KX-7429-ZEBRA" in (needle["content"] + needle["reasoning"])

# ---------- derived throughput ----------
cu = needle.get("usage", {})
ct = cu.get("completion_tokens", 0)
pt = cu.get("prompt_tokens", 0)
result["t4"] = {
    "long_episode_seconds": needle["seconds"],
    "long_prompt_tokens": pt,
    "long_completion_tokens": ct,
    "decode_tok_per_s": round(ct / needle["seconds"], 1) if needle["seconds"] else None,
    "smoke_seconds": smoke["seconds"],
    "note": "decode tok/s = completion_tokens / wall seconds (includes prefill of the "
            "long prompt; prefill dominates the first call. Use as a lower bound).",
}

json.dump(result, open(out, "w"), indent=2)
print(f"T1 needle ({name}): {'FOUND' if result['needle_found'] else 'NOT FOUND'}")
print(f"T4: long episode {needle['seconds']}s, prompt {pt} tok, completion {ct} tok, "
      f"~{result['t4']['decode_tok_per_s']} tok/s")
print("artifact:", out)
sys.exit(0 if result["needle_found"] else 1)
PYEOF
