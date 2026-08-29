# Optional Models for the ctx-32768 Path (choice 1-C) — RECORD ONLY

Status: **reference analysis, no action.** Recorded 2026-08-29 per user
instruction ("record the models in a file as optional method"). The pilot runs
at ctx 24576 (choice 1-A). This file exists so that if 32k context ever becomes
necessary, the model-selection analysis is already done.

Constraint equation (same method as the 2026-08-28 audit): one 79.19 GiB card,
util 0.90 → allocation ceiling 71.27 GiB; R12 requires ≥ 7.92 GiB free →
**weights + KV(32k) + ~3 GiB runtime overhead ≤ 63.35 GiB**.

## First, what 32768 costs the CURRENT lineup

| model | KV/token | weights+KV(32k)+3 GiB | ≤ 63.35? |
|---|---|---|---|
| qwen3-32b (bf16) | 256 KiB | 64 + 8 + 3 = 75.0 | **FAILS by 11.7 GiB** |
| gemma4-31b (bf16) | hybrid, ~50 KiB eff. | 62 + 1.6 + 3 = 66.6 | **FAILS by 3.3 GiB** |
| Qwen3-30B-A3B (bf16) | 96 KiB | 57 + 3 + 3 = 63.0 | passes by 0.35 GiB — **too marginal to count as R12-pass** |
| qwen3-8b (fp16) | 144 KiB | 16 + 4.5 + 3 = 23.5 | passes |

So the 1-C path would have displaced **two** models, not one: the pair-1 large
slot AND the held-out model. (This is also the retrospective confirmation that
1-C should never have been presented as a live option — M13.)

## Replacement candidates for pair-1 large @ 32768 (fits + experiment criteria)

### Candidate 1 — Qwen/Qwen3-32B-FP8 (official FP8 checkpoint)
- Memory: weights ~32.7 GiB + KV 8 GiB (bf16 KV; 4 GiB if KV also fp8) + 3 →
  **~43.7 GiB total, ~19.6 GiB margin under the ceiling. Strong pass.**
- Experiment criteria: identical architecture, tokenizer, and behavior family to
  the original pair-1 design — the *minimal-change* swap; native 128k ctx;
  Apache-2.0; same serving image. Quantization effect (FP8 vs bf16) is a
  measurable, documentable perturbation, and the pilot already records
  precision per arm.
- Risk: FP8 dynamic-quant quality on long tool-use trajectories is the only
  open question; would need the same T1/T2 validation battery.

### Candidate 2 — mistralai/Mistral-Small-3.2-24B-Instruct-2506
- Memory: weights ~48 GiB bf16 + KV (40L, 8 KV heads, 128d → 160 KiB/tok →
  5 GiB @32k) + 3 → **~56 GiB, ~7.4 GiB margin. Passes, but near the bar.**
- Experiment criteria: native 128k ctx; Apache-2.0; **cross-family diversity**
  (non-Qwen calibrated pair-1 → stronger claim that the switch effect is not
  Qwen-specific); strong published tool-use performance.
- Risks: 24B is a capability step down from 32B (changes what the pair-1
  switch measures); margin is thin — any vLLM runtime overhead growth breaks
  R12; adds a second tokenizer/chat-format family to maintain.

### Candidate 3 — Qwen/Qwen3-14B
- Memory: ~28 + 4.5 + 3 → **~35.5 GiB, huge margin.**
- Experiment criteria: trivial fit, native 128k, same family.
- Risk: 14B vs 32B is a major capability drop; pair-1's "large" arm would no
  longer be comparable to the original design's intent. Only viable if the
  hypothesis is reframed around small-model switches.

### Rejected at pre-screen (recorded for transparency, not options)
- Llama-3.3-70B-Instruct-FP8-dynamic: 70 + 10 + 3 = 83 GiB — fails at ANY
  usable ctx (established 2026-08-28).
- Qwen2.5-32B-Instruct (bf16): same KV profile as Qwen3-32B, older generation —
  no advantage over Candidate 1's FP8 route.
- Any AWQ/GPTQ 4-bit 32B: passes memory trivially but quantization quality on
  structured tool-arg generation is unvalidated and would confound the shim
  measurements; not worth it when Candidate 1 fits with 19.6 GiB margin.

## Bottom line (record, not recommendation to act)

If 32k is ever required: **Candidate 1 (Qwen3-32B-FP8)** is the minimal-change
path and the only one that doesn't either thin the safety margin or change the
capability tier. Note that the held-out slot would ALSO need replacement
(gemma4-31b fails at 32k), so the true cost of 1-C was always two model
swaps — one more reason the pilot stays at 24576.
