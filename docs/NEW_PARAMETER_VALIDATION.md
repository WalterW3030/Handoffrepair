# New-Parameter Validation Experiment (pre-staging gate)

Scope: validate the two parameter changes of 2026-08-29 **before** the full
staging re-run consumes GPU hours on an unvalidated configuration:
1. **ctx 24576** uniform across all four models (choice 1-A).
2. **UniformToolShim** as the sole tool-call extraction layer (choice 2-C).

All tests run inside the normal staging harness (`scripts/staging_collect.sh`)
or immediately after it, reusing the already-served endpoints — no extra model
launches except where stated. Every test writes its artifact into the staging
evidence dir (R8: pushed via `tools/push_latest_evidence.sh`, never pasted).

Pass rule: **ALL of T1–T4 pass for ALL four models**, else the pilot does not
proceed to the main-run approval gate. Failures are data (logged), never
hand-patched per episode (Rule 26).

---

## T1 — Long-context integrity probe (validates ctx 24576)

Goal: prove an episode at the workload maximum survives without truncation and
that the model still responds coherently at that depth.

Method, per model:
1. Construct a synthetic ToolSandbox-style trajectory of **20,000–21,000 tokens**
   (≈ the 30-turn cap with repair-contract overhead): repeated realistic
   user/assistant/tool-result blocks from the ToolSandbox distribution, ending
   with a question whose answer is a token placed in turn 2 (needle test).
2. Send via the uniform shim path; request a completion.
3. Record: prompt_tokens actually accepted by the server, completion finish
   reason, whether the needle token is recovered, latency, peak GPU memory
   during the call.

Pass criteria:
- Server accepts ≥ 20,500 prompt tokens (no 400/context-length error).
- finish_reason = "stop" (not "length" from prompt truncation).
- Needle recovered verbatim.
- Peak memory leaves ≥ 7.9 GiB free on the card (R12 verified empirically,
  not just from spec math).

Artifact: `evidence/<ts>/t1_longctx_<model>.json` (one per model).

## T2 — Shim extraction battery (validates UniformToolShim)

Goal: the shim must extract tool calls at 100% schema validity on a frozen
probe set, for every model — this replaces the retired vLLM/sglang parser gate.

Method, per model:
1. Frozen battery of **20 probe cases** (checked into `smoke/shim_probe_20.json`,
   hash-pinned): 12 single-tool calls across the ToolSandbox tool families,
   4 no-tool "message" responses, 2 calls with nested/unicode arguments,
   2 adversarial cases (schema-shaped distractor text in the transcript).
2. Each case runs through `UniformToolShim.generate()` at temperature 0.
3. Record per case: parseable?, action type correct?, tool name correct?,
   args schema-valid?, retries used, shim_failure emitted?

Pass criteria: **20/20 per model** with zero `[shim_failure]`; retry rate is
recorded (not gated, but reported — it feeds the throughput estimate).

Artifact: `evidence/<ts>/t2_shim_<model>.json`; summary line per model in
`weight_hash_verify.yaml`-style YAML block.

## T3 — Peak-memory and headroom measurement at 24576

Goal: empirical confirmation of the R12 audit numbers (spec math → measured).

Method: during T1+T2, sample `nvidia-smi --query-gpu=memory.used` every 10 s
per model launch (the staging harness already does this); compute peak.

Pass criteria (measured peak ≤ these spec-derived ceilings, util 0.90,
79.19 GiB card):
| model | budget | predicted peak | R12 bar |
|---|---|---|---|
| qwen3-32b | 71.27 GiB | ≤ 69.4 GiB | ≥ 7.92 GiB free |
| Qwen3-30B-A3B | 71.27 GiB | ≤ 63.8 GiB | ≥ 7.92 GiB free |
| gemma4-31b | 71.27 GiB | ≤ 66.7 GiB | ≥ 7.92 GiB free |
| qwen3-8b | 71.27 GiB | ≤ 21 GiB | ≥ 7.92 GiB free |

Artifact: `evidence/<ts>/peak_memory.txt` (existing channel, now gated).

## T4 — Throughput probe (re-estimates the main-run GPU-hour cost)

Goal: replace the rough 13–16 GPU-h estimate with a measured one.

Method, per model: time T1 (one ~20.5k-token episode, prompt + generation) and
one short 8-token smoke; derive tokens/s at pilot decode settings
(temperature 0, max_new_tokens 1024, shim overhead included).

Output: `evidence/<ts>/t4_throughput.yaml` with per-model tok/s and the
recomputed main-run GPU-hour estimate; recorded in MACHINE_PROPERTIES.md
before the approval gate.

---

## Order and cost

T1/T3/T4 ride on the staging launches (no extra GPU time beyond the probes,
~5 min per model). T2 adds ~10 min per model (20 guided-JSON calls at low
temperature). Total added staging time: **≈ 1 GPU-h across all four models**.
Run order inside staging: launch → smoke → T1 → T2 → (T3/T4 computed from
logs) → next model.
