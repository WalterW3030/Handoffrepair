#!/usr/bin/env bash
# A8 — Gemma-4-31B-IT serving (held-out target). SWITCHED from Gemma-3-27B (user decision).
# Gemma 4 has NATIVE function calling (<|tool_call>...<tool_call|>), so NO prompt-shim needed.
# Apache 2.0 — no gated license (HF_TOKEN only for download-rate/telemetry, not access).
#
# KNOWN BLOCKER (P2, revised): Gemma-4 tool calling is UNRELIABLE in vLLM <= v0.24.0 and the
# native <|tool_call> format is not parsed by all servers. TWO serving paths; Day-0 picks the
# one that WORKS on the pinned version, and records which in the run log:
#
#   PATH A (vLLM, preferred). Pin a vLLM version that INCLUDES the gemma4 tool parser
#   (the early-v0.24 bugs were fixed shortly after; use the official Gemma-4 recipe).
#   The official recipe REQUIRES the dedicated chat template + reasoning parser [vLLM recipes].
set -euo pipefail
: "${VLLM_GEMMA4_OK:?set VLLM_GEMMA4_OK=1 after Day-0 verifies vLLM parses gemma-4 tool calls}"
vllm serve google/gemma-4-31b-it \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser gemma4 \
  --reasoning-parser gemma4 \
  --chat-template examples/tool_chat_template_gemma4.jinja \
  --port 8000

#   PATH B (sglang fallback, verified working for gemma-4 tool calling in community reports):
# docker run --gpus all --ipc=host --shm-size 32g -p 8000:30000 lmsysorg/sglang:v0.5.14 \
#   sglang serve --model-path google/gemma-4-31b-it --tool-call-parser gemma4 \
#     --reasoning-parser gemma4 --mem-fraction-static 0.92 --host 0.0.0.0 --port 30000
#
# Either way, the gemma_tool_shim.py prompt-fallback REMAINS as a last resort if neither parser
# works on the pinned stack — logged as interface distance in Gemma-4's capability manifest.
