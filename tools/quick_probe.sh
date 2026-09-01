#!/usr/bin/env bash
# quick_probe.sh — fast single-model vLLM launch + full crash diagnostics.
# Use this instead of the full staging_collect.sh when you just want the REAL
# reason one model dies. No weight-hash step, no smoke suite, no bundle.
#
# Usage:
#   bash tools/quick_probe.sh [model_key] [gpu_mem_util]
#     model_key     one of: qwen3-32b | qwen3-8b | qwen3-30b-a3b | gemma4-31b
#                   (default: qwen3-32b)
#     gpu_mem_util  vLLM --gpu-memory-utilization (default: 0.90)
#
# Output (always written, even on crash), to ./quick_probe_out/ :
#   serve_<key>.log   full vLLM stdout/stderr
#   diag_<key>.txt    exit_code / oom_killed / error  (the decisive bits)
#   nvidia_smi.txt    GPU memory timeline sampled during load
#
# Exit code: 0 if server became healthy, 1 otherwise (see the two files above).

set -u
cd "$(dirname "$0")/.."

# --- env ---------------------------------------------------------------------
[ -f env.sh ] && . ./env.sh
PILOT_DATA="${PILOT_DATA:-/ephemeral/hr/pilot}"
HF_HOME="${HF_HOME:-$PILOT_DATA/hf}"
IMAGE="${VLLM_IMAGE:-vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967}"
PORT="${QP_PORT:-18080}"

KEY="${1:-qwen3-32b}"
MEMUTIL="${2:-0.90}"

declare -A MODELS=(
  [qwen3-32b]="Qwen/Qwen3-32B"
  [qwen3-8b]="Qwen/Qwen3-8B"
  [qwen3-30b-a3b]="Qwen/Qwen3-30B-A3B-Instruct-2507"
  [gemma4-31b]="google/gemma-4-31B-it"
)
MODEL="${MODELS[$KEY]:-}"
[ -n "$MODEL" ] || { echo "unknown model key: $KEY (choose: ${!MODELS[*]})"; exit 2; }

OUT="quick_probe_out"
mkdir -p "$OUT"
NAME="qp_$KEY"

echo "== quick_probe: $KEY ($MODEL)  gpu-mem-util=$MEMUTIL  port=$PORT =="
echo "   image: $IMAGE"

# GPU selection (2026-08-28 evidence: cuda:0 was 33 GiB occupied by another
# process → ValueError "free memory < desired utilization", exit 1). Pick the
# freest GPU unless GPU_ID is pinned.
pick_gpu() {
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits \
    | sort -t, -k2 -n | head -1 | awk -F, '{gsub(/ /,"",$1); print $1}'
}
GPU_ID="${GPU_ID:-$(pick_gpu)}"
FREE_MIB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$GPU_ID" | head -1)
echo "   selected GPU $GPU_ID (free ${FREE_MIB} MiB; override with GPU_ID=n)"
if [ "$FREE_MIB" -lt 73000 ]; then
  echo "STOP: GPU $GPU_ID has only ${FREE_MIB} MiB free (<73 GiB needed at util $MEMUTIL)."
  echo "      Another process/tenant holds it — check nvidia-smi and retry (GPU_ID=n bash tools/quick_probe.sh $KEY)."
  exit 1
fi

# --- pre-clean any stale container of this name ------------------------------
docker rm -f "$NAME" > /dev/null 2>&1 || true

# HF token: never stored on disk/git (user decision 2026-08-28). Prompt if unset
# or polluted with non-ASCII chars; lives only in this process env.
hf_token_clean() { [ -n "${HF_TOKEN:-}" ] && ! printf '%s' "$HF_TOKEN" | LC_ALL=C grep -qP '[^\x00-\x7F]'; }
if ! hf_token_clean && [ -t 0 ]; then
  [ -n "${HF_TOKEN:-}" ] && echo "HF_TOKEN set but contains non-ASCII chars — re-enter." || echo "HF_TOKEN not set."
  tries=0
  until hf_token_clean; do
    tries=$((tries+1)); [ "$tries" -le 3 ] || { echo "STOP: HF_TOKEN still invalid after 3 attempts"; exit 1; }
    read -rsp "Enter HF_TOKEN (input hidden): " HF_TOKEN; echo
    export HF_TOKEN
    hf_token_clean || echo "  rejected: empty or non-ASCII chars — re-enter carefully."
  done
fi

# --- launch (no --rm so a crash keeps its logs; --ipc=host is required) ------
# --gpus device=$GPU_ID alone isolates to that GPU; no CUDA_VISIBLE_DEVICES.
docker run -d --name "$NAME" --gpus "\"device=$GPU_ID\"" \
  --ipc=host \
  -e VLLM_ENABLE_CUDA_COMPATIBILITY=1 \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" \
  ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  "$IMAGE" \
  "$MODEL" --served-model-name "$KEY" \
  --max-model-len 16384 --gpu-memory-utilization "$MEMUTIL" --enforce-eager \
  > /dev/null || { echo "STOP: docker run failed (see 'docker ps -a')"; exit 1; }

echo "   launched container $NAME — watching for health or death (up to 20 min)..."

# --- GPU memory timeline (background) ----------------------------------------
( for _ in $(seq 1 120); do
    echo "$(date +%H:%M:%S) $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU_ID") MiB"
    sleep 10
  done ) > "$OUT/nvidia_smi.txt" 2>/dev/null &
SMI_PID=$!

capture_diag() {
  docker logs "$NAME" > "$OUT/serve_${KEY}.log" 2>&1 || true
  { echo "exit_code=$(docker inspect -f '{{.State.ExitCode}}' "$NAME" 2>/dev/null)";
    echo "oom_killed=$(docker inspect -f '{{.State.OOMKilled}}' "$NAME" 2>/dev/null)";
    echo "error=$(docker inspect -f '{{.State.Error}}' "$NAME" 2>/dev/null)";
    echo "finished_at=$(docker inspect -f '{{.State.FinishedAt}}' "$NAME" 2>/dev/null)"; } \
    > "$OUT/diag_${KEY}.txt" 2>/dev/null || true
}

# --- watch loop ---------------------------------------------------------------
ready=0
for _ in $(seq 1 120); do   # 20 min
  sleep 10
  if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
    capture_diag
    kill $SMI_PID 2>/dev/null || true
    echo
    echo "== SERVER DIED =="
    echo "--- diag_${KEY}.txt ---"; cat "$OUT/diag_${KEY}.txt"
    echo "--- tail of serve_${KEY}.log ---"; tail -40 "$OUT/serve_${KEY}.log"
    echo
    echo "How to read it:"
    echo "  oom_killed=true            -> out of memory (lower gpu-mem-util, e.g. try: bash tools/quick_probe.sh $KEY 0.80)"
    echo "  exit_code=137,oom=false    -> killed (often shm/IPC; --ipc=host already set, or host OOM)"
    echo "  exit_code=139              -> segfault (engine/kernel issue)"
    echo "  exit_code=1                -> config/arg/auth error (read the log tail above)"
    docker rm -f "$NAME" > /dev/null 2>&1 || true
    exit 1
  fi
  if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then ready=1; break; fi
done

kill $SMI_PID 2>/dev/null || true
capture_diag

if [ "$ready" = 1 ]; then
  echo
  echo "== HEALTHY =="; echo "  $KEY is serving on port $PORT."
  echo "  quick smoke:"
  curl -s "http://localhost:$PORT/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$KEY\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":8}" \
    | tee "$OUT/smoke_${KEY}.json"
  echo
  echo "  (leaving container running; stop with:  docker rm -f $NAME)"
  exit 0
else
  echo "== HEALTH TIMEOUT (20 min) =="; echo "  see $OUT/serve_${KEY}.log"
  docker rm -f "$NAME" > /dev/null 2>&1 || true
  exit 1
fi
