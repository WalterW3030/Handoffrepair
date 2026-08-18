# Future RC tag package — prepared, NOT tagged (R5)

**Status:** draft only. Tag is created ONLY after staging evidence (Phase B) exists.
`pilot-freeze-v1` (bbe8030) stays archived forever — never moved, never overwritten.

## Proposed tag

- **Name:** `pilot-rc-v2` (new immutable release candidate; supersedes nothing — v1 remains as the archived RC)
- **Target:** the HEAD containing staging evidence commits (B5 package)
- **Message draft:**

```
pilot-rc-v2 — immutable release candidate (staging-verified)

Frozen bundle, all values evidence-backed:
- models: Qwen3-32B 9216db57 / Qwen3-8B b968826d / Llama-3.3-70B-FP8 f50dbad2 / gemma-4-31B-it 842da379
- weights: 39-file sha256 lock VERIFIED on staging machine
- container: vllm/vllm-openai@sha256:0a51ea5b… RE-VERIFIED on H100 (digest match)
- episodes: 78 kept scenarios, ToolSandbox 165848b9
- manifest: 1,180 runs, MEASURED rates (kind=gpu_measured), ≤20h cap
- staging: launch logs + peak memory (4 models), gemma4 probe gate result attached
- pilot-freeze-v1 archived at bbe8030 (unchanged)
```

## Values that MUST come from staging before tagging (currently blank by design)

| Field | Source |
|---|---|
| `logs/measured_rates.json` kind=gpu_measured | B4 calibration on H100 |
| Peak memory per model | B3 launch smoke |
| gemma4 probe gate verdict (vllm / sglang / shim) | B3 probe set |
| Digest re-verification line | B1 docker inspect on machine |

## Pre-tag checklist (mechanical)

1. `grep -rn "TBD" configs/ staging_smoke_runsheet.md` → empty
2. Fresh clone → `pip install -r requirements-lock.txt` → 18/18 tests
3. Dry-run assertions A1/A2 PASS on the machine's ToolSandbox checkout
4. Staging evidence files committed (B5 list)
5. Advisor main-run approval logged in the ledger
