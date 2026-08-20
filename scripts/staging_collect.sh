#!/usr/bin/env bash
# staging_collect.sh — run the approved M1 staging (run sheet §0-§3) and pack
# all evidence into one tarball to upload back for verification.
# Auto-STOPs (exit 1) on: container digest mismatch, weight hash mismatch,
# server crash, or health timeout. Run from the repo root after setup_machine.sh.
set -uo pipefail
cd "$(dirname "$0")/.."

IMAGE="vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
EXPECT_DIGEST="sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EV="staging_evidence/$STAMP"
mkdir -p "$EV"
echo "evidence dir: $EV"

stop () { echo "STOP: $1" | tee -a "$EV/STOP.txt"; exit 1; }

echo "== [0/4] environment record =="
{
  date -u; uname -a
  nvidia-smi || stop "nvidia-smi failed — driver not working"
  docker version || stop "docker not working (install docker + nvidia-container-toolkit)"
  docker info 2>/dev/null | grep -i runtime
  python3 --version; df -h .; free -g
  echo "RAPID_API_KEY set: ${RAPID_API_KEY:+yes}${RAPID_API_KEY:-NO (needed later for main run, not for staging)}"
} > "$EV/env.txt" 2>&1 || stop "environment record failed"
cat "$EV/env.txt"

echo "== [1/4] pull pinned vLLM image and verify digest =="
docker pull "$IMAGE" | tee "$EV/docker_pull.log" || stop "docker pull failed"
ACTUAL=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE" | sed 's/.*@//')
echo "expected=$EXPECT_DIGEST"
echo "actual=$ACTUAL"
{ echo "expected=$EXPECT_DIGEST"; echo "actual=$ACTUAL"; } | tee "$EV/digest_check.txt"
[ "$ACTUAL" = "$EXPECT_DIGEST" ] || stop "container digest mismatch"

echo "== [2/4] verify weights against configs/weight_sha256.lock =="
python3 tools/hash_weights.py --out "$EV/weight_hash_verify.yaml" \
  || stop "weight hash verification failed — do NOT proceed, see $EV/weight_hash_verify.yaml"

echo "== [3/4] per-model launch smoke + peak memory + probes =="
KEYS=(qwen3-32b qwen3-8b llama33-70b-fp8 gemma4-31b)
declare -A MODELS=(
  [qwen3-32b]="Qwen/Qwen3-32B"
  [qwen3-8b]="Qwen/Qwen3-8B"
  [llama33-70b-fp8]="RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic"
  [gemma4-31b]="google/gemma-4-31B-it"
)
PORT=18080
: > "$EV/peak_memory.txt"
for key in "${KEYS[@]}"; do
  model="${MODELS[$key]}"
  echo "--- $key ($model) on port $PORT"
  docker run -d --rm --name "staging_$key" --gpus all \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -p "$PORT:8000" \
    ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
    "$IMAGE" \
    --model "$model" --served-model-name "$key" \
    --max-model-len 8192 --gpu-memory-utilization 0.95 --enforce-eager \
    > /dev/null || stop "docker run failed for $key"

  ready=0; peak=0
  for _ in $(seq 1 180); do   # up to 30 min
    sleep 10
    if ! docker ps --format '{{.Names}}' | grep -qx "staging_$key"; then
      docker logs "staging_$key" > "$EV/serve_${key}.log" 2>&1 || true
      stop "server died for $key — see $EV/serve_${key}.log"
    fi
    mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)
    [ "$mem" -gt "$peak" ] && peak=$mem
    if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then ready=1; break; fi
  done
  docker logs "staging_$key" > "$EV/serve_${key}.log" 2>&1 || true
  [ "$ready" = 1 ] || stop "health timeout (30 min) for $key — see $EV/serve_${key}.log"

  curl -s "http://localhost:$PORT/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$key\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":8}" \
    | tee "$EV/smoke_${key}.json" > /dev/null
  echo >> "$EV/smoke_${key}.json"

  if [ "$key" = gemma4-31b ]; then
    echo "    (gemma4 tool-call probe)"
    curl -s "http://localhost:$PORT/v1/chat/completions" \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"$key\",\"messages\":[{\"role\":\"user\",\"content\":\"What is the weather in Paris? Use the tool.\"}],\"max_tokens\":128,\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"get_weather\",\"description\":\"Get weather for a city\",\"parameters\":{\"type\":\"object\",\"properties\":{\"city\":{\"type\":\"string\"}},\"required\":[\"city\"]}}}]}" \
      | tee "$EV/gemma4_toolcall_probe.json" > /dev/null
    echo >> "$EV/gemma4_toolcall_probe.json"
    grep -iE "tool|chat.template|parser" "$EV/serve_${key}.log" | head -50 > "$EV/gemma4_probe_log_excerpt.txt" || true
  fi

  sleep 5
  mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)
  [ "$mem" -gt "$peak" ] && peak=$mem
  echo "$key peak_mib=$peak" | tee -a "$EV/peak_memory.txt"
  docker stop "staging_$key" > /dev/null
  PORT=$((PORT+1))
done

echo "== [4/4] bundle =="
BUNDLE="staging_evidence_$STAMP.tar.gz"
tar czf "$BUNDLE" -C staging_evidence "$STAMP"
echo
echo "STAGING DONE — upload this file back to the chat:  $BUNDLE"
[ -f "$EV/STOP.txt" ] && exit 1 || exit 0
