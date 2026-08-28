#!/usr/bin/env bash
# serve_llama33_70b.sh — RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic via the digest-pinned
# vLLM container, one GPU, freest auto-selected (R3). Rewritten 2026-08-20 (see serve_qwen3_8b.sh header).
# Official prequantized FP8 checkpoint — single ~80GB GPU only; A100 lacks FP8 tensor cores.
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
exec docker run --rm --name serve_llama33_70b --gpus '"'"device=$GPU_ID"'"' \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  "$IMAGE" \
  RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic \
  --revision f50dbad2c84590ca17dc51e207c34321b65ff14b \
  --served-model-name llama33-70b-fp8 \
  --max-model-len 8192 --gpu-memory-utilization 0.90 --enforce-eager \
  --enable-auto-tool-choice --tool-call-parser llama3_json
