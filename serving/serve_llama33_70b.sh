#!/usr/bin/env bash
# serve_llama33_70b.sh — RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic via the digest-pinned
# vLLM container, GPU 0 only (R3). Rewritten 2026-08-20 (see serve_qwen3_8b.sh header).
# Official prequantized FP8 checkpoint — single ~80GB GPU only; A100 lacks FP8 tensor cores.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f env.sh ] && source env.sh
export CUDA_VISIBLE_DEVICES=0   # R3
IMAGE="vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
HF_HOME="${HF_HOME:-/ephemeral/$USER/hf}"
PORT="${PORT:-8000}"
exec docker run --rm --name serve_llama33_70b --gpus '"device=0"' \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" -e CUDA_VISIBLE_DEVICES=0 ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  "$IMAGE" \
  --model RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic \
  --revision f50dbad2c84590ca17dc51e207c34321b65ff14b \
  --served-model-name llama33-70b-fp8 \
  --max-model-len 8192 --gpu-memory-utilization 0.95 --enforce-eager \
  --enable-auto-tool-choice --tool-call-parser llama3_json
