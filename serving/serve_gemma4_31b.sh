#!/usr/bin/env bash
# serve_gemma4_31b.sh — google/gemma-4-31B-it (held-out target) via the digest-pinned vLLM
# container, one GPU, freest auto-selected (R3).
#
# 2026-08-31 — gemma4 startup fix = OPTION B (user decision): the pinned v0.27.1 image ships
# transformers >= 5.15, whose heterogeneity guard makes head_dim a per-layer attribute; vLLM
# 0.27.1's config converter reads the global head_dim and crashes with
# AmbiguousGlobalPerLayerAttributeError (upstream #51744 / #52768). Fix: pin transformers==5.14.1
# INSIDE THE CONTAINER at startup (verified fix in #51744). Applied HERE ONLY — the other three
# models keep the frozen image untouched, so their staging results remain valid.
#
# FALLBACK — OPTION A (documented, NOT active): dedicated image vllm/vllm-openai:gemma4-cu130,
# digest-pinned at staging time. Use ONLY if B fails staging. See docs/GEMMA4_FIX_OPTIONS.md.
#
# Tool-call extraction: UniformToolShim (user decision 2026-08-29, choice 2-C) — NO engine
# parsers; --enable-auto-tool-choice/--tool-call-parser/--reasoning-parser/--chat-template
# all removed 2026-08-31 to match the other three launchers.
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
exec docker run --rm --name serve_gemma4_31b --gpus '"'"device=$GPU_ID"'"' \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  --ipc=host \
  -e VLLM_ENABLE_CUDA_COMPATIBILITY=1 \
  --entrypoint /bin/bash \
  "$IMAGE" \
  -c 'pip install --no-cache-dir -q "transformers==5.14.1" && exec vllm serve \
  google/gemma-4-31B-it \
  --revision 842da3794eaa0b77d5f08bae87a17459d91ff475 \
  --served-model-name gemma4-31b \
  --max-model-len 16384 --gpu-memory-utilization 0.92 --enforce-eager'
