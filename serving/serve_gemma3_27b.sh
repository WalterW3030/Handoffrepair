#!/usr/bin/env bash
# A8 — Gemma-3-27B-IT serving (held-out target). Prerequisite P2:
# Gemma 3 has NO native tool-call tokens — tool calling is prompt-based JSON,
# enforced parseable via the shim (gemma_tool_shim.py) + structured outputs.
# Deliberately NO --enable-auto-tool-choice here: the shim owns the protocol.
set -euo pipefail
: "${HF_TOKEN:?HF_TOKEN must be set (gated model)}"
vllm serve google/gemma-3-27b-it \
  --max-model-len 32768 \
  --enable-prefix-caching \
  --port 8000
