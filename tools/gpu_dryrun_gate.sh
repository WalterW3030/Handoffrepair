#!/usr/bin/env bash
# gpu_dryrun_gate.sh — M28 gate: prove the GPU run path end-to-end BEFORE the main run.
#
# Runs ONE real episode (b0, first pilot episode, seed 1) against live served models
# and verifies the record is REAL: model names are the served names (not mock-source/
# mock-target), usage tokens > 0, at least one tool_call step executed. Without this,
# a mis-wired runner produces instant perfect FAKE results (the M28 failure mode).
#
# Usage:  bash tools/gpu_dryrun_gate.sh <pair_key>
#   pair_key: pair1_32to8 | pair2_30to8 | heldout_32to31
# Requires: the pair's source+target models AND qwen3-8b (user sim) served on the
#   ports in configs/decoding.yaml:vllm_endpoints; ToolSandbox repo present.
# Output: evidence/gpu_dryrun_<pair>_<ts>.json. Exit 0 iff the record is real.
set -euo pipefail
cd "$(dirname "$0")/.."
PAIR="${1:?usage: gpu_dryrun_gate.sh <pair_key>}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="evidence/gpu_dryrun_${PAIR}_${TS}.json"
mkdir -p evidence logs
python3 - "$PAIR" "$OUT" << 'PYEOF'
import json, sys
sys.path.insert(0, "src")
sys.path.insert(0, "src/toolsandbox")
import run_pilot
from executor import load_scenarios

pair, out = sys.argv[1], sys.argv[2]
run = {"pair": pair, "column": "B0", "switch_point": None,
       "episode_id": run_pilot.load_episodes()[0], "seed": 1}
run_pilot._require_endpoints([run])          # hard-fails if any needed model is down
scenarios = load_scenarios("/opt/ToolSandbox")
rec = run_pilot._execute_run(run, scenarios, "/opt/ToolSandbox", "gpu")

checks = {
    "model_source_is_served": rec["model_source"] == run_pilot.PAIRS[pair][0],
    "model_target_is_served": rec["model_target"] == run_pilot.PAIRS[pair][1],
    "not_mock": rec["model_source"] != "mock-source" and rec["mode"] == "gpu_vllm",
    "usage_nonzero": rec["usage"]["prompt_tokens"] > 0,
    "has_tool_step": any(s.get("type") == "tool_call" for s in rec["steps"]),
}
ok = all(checks.values())
json.dump({"pair": pair, "ts": out, "checks": checks, "verdict": "PASS" if ok else "FAIL",
           "record_summary": {"model_source": rec["model_source"],
                              "model_target": rec["model_target"],
                              "n_steps": len(rec["steps"]),
                              "shim_failures": rec.get("shim_failures"),
                              "usage": rec["usage"], "wall_sec": rec["wall_sec"],
                              "score": rec["score"]["similarity"]}},
          open(out, "w"), indent=2)
print(("PASS" if ok else "FAIL"), json.dumps(checks))
print("artifact:", out)
sys.exit(0 if ok else 1)
PYEOF
