#!/usr/bin/env bash
# A8 — Llama-3.3-70B-Instruct serving (source in calibrated pair 2).
# FP8 is MANDATORY on a single 80GB card (~70GB weights); FP16 does not fit.
# Requires HF_TOKEN env (gated repo, license accepted at prerequisite P5).
set -euo pipefail
: "${HF_TOKEN:?HF_TOKEN must be set (gated model)}"
vllm serve meta-llama/Llama-3.3-70B-Instruct \
  --quantization fp8 \
  --max-model-len 32768 \
  --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser llama3_json \
  --port 8000
