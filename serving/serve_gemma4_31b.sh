#!/usr/bin/env bash
# serve_gemma4_31b.sh — google/gemma-4-31B-it (held-out target) via the digest-pinned vLLM
# container, one GPU, freest auto-selected (R3). Rewritten 2026-08-20 (see serve_qwen3_8b.sh header).
# Gemma 4 has native function calling; the gemma4 tool parser path is verified at staging
# (gemma4_toolcall_probe.json). If the probe fails, serving/gemma_tool_shim.py is the
# last-resort fallback — logged as interface distance, never hand-patched per call (Rule 26).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f env.sh ] && source env.sh
: "${VLLM_GEMMA4_OK:?set VLLM_GEMMA4_OK=1 only after the staging gemma4 tool-call probe passes}"
# R3: exactly one GPU — pick the freest unless GPU_ID is pinned (shared 8-GPU machine;
# 2026-08-28: cuda:0 was 33 GiB occupied by another process → vLLM refused to start).
GPU_ID="${GPU_ID:-$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | sort -t, -k2 -n | head -1 | awk -F, '{gsub(/ /,"",$1); print $1}')}"
IMAGE="vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
HF_HOME="${HF_HOME:-${PILOT_DATA:-/ephemeral/hr/pilot}/hf}"
PORT="${PORT:-8000}"
exec docker run --rm --name serve_gemma4_31b --gpus '"'"device=$GPU_ID"'"' \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -v "$PWD/examples:/templates:ro" \
  -p "$PORT:8000" ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  --ipc=host \
  -e VLLM_ENABLE_CUDA_COMPATIBILITY=1 \  # driver R570 (CUDA≤12.8) vs image CUDA 13.0.2
  "$IMAGE" \
  google/gemma-4-31B-it \
  --revision 842da3794eaa0b77d5f08bae87a17459d91ff475 \
  --served-model-name gemma4-31b \
  --max-model-len 24576 --gpu-memory-utilization 0.90 --enforce-eager \
  --reasoning-parser gemma4 \
  --chat-template /templates/tool_chat_template_gemma4.jinja
