#!/usr/bin/env bash
# A8/ITEM3 — Llama-3.3-70B serving (source in calibrated pair 2).
# OFFICIAL PREQUANTIZED checkpoint (Red Hat validated FP8-dynamic) — pinned, no recipe to drift.
# Single H100 80GB ONLY: A100 lacks FP8 tensor cores and would fall back to FP16 (not equivalent).
# max-model-len capped at 16384 so the FP8 KV pool fits the 80GB envelope (~70GB weights + KV).
# Requires HF_TOKEN env (gated repo, license accepted at prerequisite P5).
set -euo pipefail
: "${HF_TOKEN:?HF_TOKEN must be set (gated model)}"
vllm serve RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser llama3_json \
  --port 8000
