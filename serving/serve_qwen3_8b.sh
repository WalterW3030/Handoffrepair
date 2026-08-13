#!/usr/bin/env bash
# A8 — Qwen3-8B serving (target in calibrated pair 1; also the Day-1 smoke model).
set -euo pipefail
vllm serve Qwen/Qwen3-8B \
  --max-model-len 32768 \
  --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --port 8000
