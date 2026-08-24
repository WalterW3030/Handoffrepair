#!/usr/bin/env bash
# quick_probe.sh — fast single-model vLLM launch + full crash diagnostics.
# Use this instead of the full staging_collect.sh when you just want the REAL
# reason one model dies. No weight-hash step, no smoke suite, no bundle.
#
# Usage:
#   bash tools/quick_probe.sh [model_key] [gpu_mem_util]
#     model_key     one of: qwen3-32b | qwen3-8b | llama33-70b-fp8 | gemma4-31b
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
  [llama33-70b-fp8]="RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic"
  [gemma4-31b]="google/gemma-4-31B-it"
)
MODEL="${MODELS[$KEY]:-}"
[ -n "$MODEL" ] || { echo "unknown model key: $KEY (choose: ${!MODELS[*]})"; exit 2; }

OUT="quick_probe_out"
mkdir -p "$OUT"
NAME="qp_$KEY"

echo "== quick_probe: $KEY ($MODEL)  gpu-mem-util=$MEMUTIL  port=$PORT =="
echo "   image: $IMAGE"

# --- pre-clean any stale container of this name ------------------------------
docker rm -f "$NAME" > /dev/null 2>&1 || true

# --- launch (no --rm so a crash keeps its logs; --ipc=host is required) ------
docker run -d --name "$NAME" --gpus '"device=0"' \
  --ipc=host \
  -v "$HF_HOME:/root/.cache/huggingface" \
  -p "$PORT:8000" \
  -e CUDA_VISIBLE_DEVICES=0 \
  ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  "$IMAGE" \
  "$MODEL" --served-model-name "$KEY" \
  --max-model-len 8192 --gpu-memory-utilization "$MEMUTIL" --enforce-eager \
  > /dev/null || { echo "STOP: docker run failed (see 'docker ps -a')"; exit 1; }

echo "   launched container $NAME — watching for health or death (up to 20 min)..."

# --- GPU memory timeline (background) ----------------------------------------
( for _ in $(seq 1 120); do
    echo "$(date +%H:%M:%S) $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1) MiB"
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
