# Repo Script Audit — structure, filename, and rules compliance
Date: 2026-08-20 · Repo HEAD at audit: `96569f5` · Rules checked: R1 (awareness), R2 (no sudo), R3 (1 GPU), R4 (venv), R5 (safe commands only)

## 1. Structure inventory (recorded)

```
handoffrepair-pilot/
├── scripts/                     # machine-day entry points
│   ├── setup_machine.sh         # one-time setup: env, ToolSandbox clone, deps, weights, hash verify
│   └── staging_collect.sh       # approved M1 staging: digest match, CUDA probe, per-model smoke, evidence bundle
├── serving/                     # per-model serving launchers
│   ├── serve_qwen3_8b.sh
│   ├── serve_qwen3_32b.sh
│   ├── serve_llama33_70b.sh
│   ├── serve_gemma4_31b.sh
│   └── gemma_tool_shim.py       # last-resort prompt-JSON fallback for gemma4 (kept, fallback only)
├── smoke/run_smoke.py           # CPU end-to-end smoke (5 episodes × B0+B1×S1-S3), pairing + schema asserts
├── src/                         # pilot code
│   ├── run_pilot.py             # 4-phase driver (mock/gpu modes)
│   ├── runner.py  ledger.py  logging_.py  prefix_cache.py  switch_points.py  world.py
│   ├── manifest.py  gate.py  analysis.py  audit.py  compiler.py
│   ├── mock_model.py  user_simulator.py  vllm_client.py
│   ├── columns/{b0,b1,b2a,b3}.py
│   ├── scoring/{dag.py, synthetic_episodes.py}
│   └── toolsandbox/{dry_run.py, executor.py, select_scenarios.py}
├── tools/hash_weights.py        # 39-file SHA-256 verification against lock (YAML)
├── tests/{test_pilot.py, test_scorer.py, test_toolsandbox_dryrun.py}
├── configs/                     # episodes{,_pilot}, sizing, models, seeds, decoding, switch_points,
│                                #   eval_frozen, spec_v3_frozen, weight_sha256.lock   ← all referenced names exist
├── examples/tool_chat_template_gemma4.jinja
├── logs/                        # evidence outputs (pilot_runs.jsonl, mock_soak_report.json, …)
├── docs/                        # EXECUTION_RULES.md, MACHINE_PROPERTIES.md, ENVIRONMENT.md, records/
├── staging_smoke_runsheet.md  VERIFY.md  RC_TAG_PACKAGE.md  requirements-lock.txt
```

**Filename cross-check:** every filename referenced by any script exists: `configs/{episodes_pilot,episodes,sizing,models,seeds,decoding,switch_points,eval_frozen}.yaml`, `configs/weight_sha256.lock`, `examples/tool_chat_template_gemma4.jinja`, `tools/hash_weights.py`, `env.sh` (created by setup). Log outputs (`pilot_runs.jsonl`, `measured_rates.json`, …) are written under `logs/`, inside the workspace. ✅

## 2. Safety scan result (whole repo, before fixes)
- **No destructive commands anywhere**: no `rm`, no `sudo`, no `docker prune`, no `kill`/`pkill`, no `subprocess`/`os.system` in Python, no writes outside the workspace (only the HF cache via `HF_HOME`, which is intended). ✅ R2/R5 clean.
- `docker run --rm` / `docker stop` in staging only touch containers the script itself created (`staging_*` names). ✅

## 3. Violations found — listed first, then fixed (commit `TBD`)
| # | File | Violation |
|---|---|---|
| V1 | `serving/serve_qwen3_8b.sh`, `serve_qwen3_32b.sh`, `serve_llama33_70b.sh`, `serve_gemma4_31b.sh` | Host-side `vllm serve` — assumed vllm installed on host (contradicts container-only design + R4); no single-GPU pin (R3); **model revision unpinned at serve time** (would pull latest weights, breaking the 39-file lock, R1); no `HF_HOME` → cache would land on the 11 G root disk; params (16384/0.92) drifted from staging pins (8192/0.95) |
| V2 | `serving/serve_gemma4_31b.sh` (commented PATH B) | Commented `docker run --gpus all` — latent R3 violation if ever uncommented |
| V3 | `serving/serve_qwen3_32b.sh` | Suggested on-the-fly `--quantization fp8` — served weights would no longer match the locked snapshot (R1) |

**Fix applied (no files deleted, per R5 — bodies rewritten in place):** all four `serve_*.sh` rewritten as thin compliant launchers: digest-pinned container, `--gpus '"device=0"'` + `CUDA_VISIBLE_DEVICES=0`, `--revision` pinned verbatim from `configs/weight_sha256.lock`, HF cache on `/ephemeral`, staging-pinned launch params, gemma template mounted read-only. The sglang PATH-B comment was removed (the shim remains the documented last resort). `gemma_tool_shim.py` unchanged (pure Python, no side effects).

## 4. Remaining notes
- `smoke/run_smoke.py`, all of `src/`, `tools/hash_weights.py`, `scripts/*.sh`: compliant; write only inside the repo/logs or the HF cache.
- Any future script touching anything outside the workspace must go through the user first (R5).
