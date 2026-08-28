#!/usr/bin/env bash
# serve_qwen3_32b.sh — Qwen3-32B via the digest-pinned vLLM container, one GPU, freest auto-selected (R3).
# Rewritten 2026-08-20 (see serve_qwen3_8b.sh header). Full-precision weights are the pinned
# lock contents (~64GB bf16); on an 80GB GPU keep max-model-len 8192 (staging pin).
# If precision is ever changed, it MUST be re-locked in configs/weight_sha256.lock first.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f env.sh ] && source env.sh
# R3: exactly one GPU — pick the freest unless GPU_ID is pinned (shared 8-GPU machine;
# 2026-08-28: cuda:0 was 33 GiB occupied by another process → vLLM refused to start).
GPU_ID="${GPU_ID:-$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | sort -t, -k2 -n | head -1 | awk -F, '{gsub(/ /,"",$1); print $1}')}"
IMAGE="vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
HF_HOME="${HF_HOME:-${PILOT_DATA:-/ephemeral/hr/pilot}/hf}"
PORT="${PORT:-8000}"
exec docker run --rm --name serve_qwen3_32b --gpus '"'"device=$GPU_ID"'"' \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  "$IMAGE" \
  Qwen/Qwen3-32B \
  --revision 9216db5781bf21249d130ec9da846c4624c16137 \
  --served-model-name qwen3-32b \
  --max-model-len 8192 --gpu-memory-utilization 0.90 --enforce-eager \
  --enable-auto-tool-choice --tool-call-parser hermes
