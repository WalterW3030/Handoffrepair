#!/usr/bin/env bash
# A8 — Qwen3-32B serving (source in pairs 1&2, held-out source). H100/A100 80GB.
# FP8 keeps VRAM ~32GB; FP16 (~64GB) also fits — whichever is chosen MUST be
# recorded in configs/models.yaml (precision is part of the version pin).
set -euo pipefail
vllm serve Qwen/Qwen3-32B \
  --quantization fp8 \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --port 8000
