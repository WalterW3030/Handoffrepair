#!/usr/bin/env bash
# serve_qwen3_30b_a3b.sh — Qwen/Qwen3-30B-A3B-Instruct-2507 via the digest-pinned
# vLLM container, one GPU, freest auto-selected (R3).
#
# 2026-08-28: REPLACES RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic as the large
# member of calibrated_pair_2. Llama-70B-FP8 (~70 GiB weights) could not satisfy
# R12 headroom on one 79.19 GiB card at any valid context length (real log:
# "2.5 GiB KV needed for 8192, only 1.04 GiB available").
# This model: MoE 30.5B total / 3.3B active, 48 layers, 4 KV heads, bf16
# (~57 GiB weights), native 262144 ctx, Apache-2.0, hermes tool parser.
#
# REVISION PIN: not yet pinned (weights not yet downloaded; HF unreachable from
# the sandbox). After the FIRST staging download, run tools/hash_weights.py,
# fill configs/weight_sha256.lock, then set QWEN3_30B_A3B_REV below to the
# commit hash and remove the "TO_PIN" fallback. Until then the script serves
# without --revision (staging only — never for the main run).
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
REV="${QWEN3_30B_A3B_REV:-TO_PIN}"
REV_ARGS=()
if [ "$REV" != "TO_PIN" ]; then
  REV_ARGS=(--revision "$REV")
else
  echo "WARN: QWEN3_30B_A3B_REV not pinned — staging only; pin before main run." >&2
fi
exec docker run --rm --name serve_qwen3_30b_a3b --gpus '"'"device=$GPU_ID"'"' \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  --ipc=host \
  -e VLLM_ENABLE_CUDA_COMPATIBILITY=1 \
  "$IMAGE" \
  Qwen/Qwen3-30B-A3B-Instruct-2507 \
  "${REV_ARGS[@]}" \
  --served-model-name qwen3-30b-a3b \
  --max-model-len 24576 --gpu-memory-utilization 0.90 --enforce-eager \
