# New-Parameter Validation Experiment (pre-staging gate)

Scope: validate the two parameter changes of 2026-08-29 **before** the full
staging re-run consumes GPU hours on an unvalidated configuration:
1. **ctx 16384** uniform across all four models (revised 2026-09-01 from 24576
   under R0/M17: gemma4's measured KV — 0.632 GiB/1k ctx — makes 24576
   infeasible on one card; 16384 at util 0.92 fits with ~0.7 GiB margin).
2. **UniformToolShim** as the sole tool-call extraction layer (choice 2-C).

All tests run inside the normal staging harness (`scripts/staging_collect.sh`)
or immediately after it, reusing the already-served endpoints — no extra model
launches except where stated. Every test writes its artifact into the staging
evidence dir (R8: pushed via `tools/push_latest_evidence.sh`, never pasted).

Pass rule: **ALL of T1–T4 pass for ALL four models**, else the pilot does not
proceed to the main-run approval gate. Failures are data (logged), never
hand-patched per episode (Rule 26).

---

## T1 — Long-context integrity probe (validates ctx 16384)

Goal: prove an episode at the workload's *average-plus* length survives without
truncation and that the model still responds coherently at that depth. (Under
R0 the design ctx is 16384, not the 20.6k workload maximum — the >16k tail is
an accepted, measured limitation; T1 validates the ctx we actually run.)

Method, per model:
1. Construct a synthetic ToolSandbox-style trajectory of **15,500–16,000 tokens**
   (just under the 16384 cap): repeated realistic user/assistant/tool-result
   blocks from the ToolSandbox distribution, ending with a question whose answer
   is a token placed in turn 2 (needle test).
2. Send via the uniform shim path; request a completion.
3. Record: prompt_tokens actually accepted by the server, completion finish
   reason, whether the needle token is recovered, latency, peak GPU memory
   during the call.

Pass criteria:
- Server accepts ≥ 15,500 prompt tokens (no 400/context-length error).
- finish_reason = "stop" (not "length" from prompt truncation).
- Needle recovered verbatim.
- Peak memory leaves the card under its measured safe ceiling (per-model,
  recorded in T3).

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

## T3 — Peak-memory and headroom measurement at 16384

Goal: empirical confirmation that each model serves at ctx 16384 / util 0.92.
Ceilings are from the 2026-08-31 staging peaks (measured) plus the ctx delta —
not from spec estimates (M15 lesson).

Pass criteria (measured peak must stay under the card's 79.19 GiB with the
largest observed margin of the run recorded; util 0.92, one card):
| model | 2026-08-31 measured peak | gate at 16384/0.92 |
|---|---|---|
| qwen3-32b | 75013 MiB (73.25 GiB) | ≤ 75013 MiB (ctx lower → only down) |
| qwen3-8b | 75471 MiB (73.70 GiB) | ≤ 75471 MiB |
| Qwen3-30B-A3B | 73819 MiB (72.09 GiB) | ≤ 73819 MiB |
| gemma4-31b | did not serve (KV fail @24576) | must serve; KV pool 11.07 GiB ≥ 10.36 need |

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
