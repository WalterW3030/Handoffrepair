#!/usr/bin/env bash
# serve_qwen3_8b.sh — Qwen3-8B via the digest-pinned vLLM container, GPU 0 only (R3).
# Rewritten 2026-08-20: the old host-side `vllm serve` version violated R1/R3/R4 and the
# weight lock (unpinned revision, host vllm, all GPUs). Container-only serving by design.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f env.sh ] && source env.sh
export CUDA_VISIBLE_DEVICES=0   # R3
IMAGE="vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
HF_HOME="${HF_HOME:-${PILOT_DATA:-/ephemeral/hr/pilot}/hf}"
PORT="${PORT:-8000}"
exec docker run --rm --name serve_qwen3_8b --gpus '"device=0"' \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" -e CUDA_VISIBLE_DEVICES=0 ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  "$IMAGE" \
  Qwen/Qwen3-8B \
  --revision b968826d9c46dd6066d109eabc6255188de91218 \
  --served-model-name qwen3-8b \
  --max-model-len 8192 --gpu-memory-utilization 0.95 --enforce-eager \
  --enable-auto-tool-choice --tool-call-parser hermes
