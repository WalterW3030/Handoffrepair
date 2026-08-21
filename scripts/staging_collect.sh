#!/usr/bin/env bash
# staging_collect.sh — run the approved M1 staging (run sheet §0-§3) and pack
# all evidence into one tarball to upload back for verification.
# Auto-STOPs (exit 1) on: container digest mismatch, CUDA/driver mismatch,
# weight hash mismatch, server crash, or health timeout.
# Rules: R2 no sudo · R3 exactly 1 GPU (--gpus '"device=0"' + CUDA_VISIBLE_DEVICES=0).
# Run from the repo root after setup_machine.sh.
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f env.sh ] && source env.sh
export CUDA_VISIBLE_DEVICES=0   # Rule R3
PY="${PILOT_PYTHON:-}"          # Rule R4: interpreter chosen by setup (conda env or .venv)
if [ -z "$PY" ]; then
  if [ -n "${CONDA_PREFIX:-}" ]; then PY="$(which python)"
  elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
  else echo "no pilot python env — run scripts/setup_machine.sh first"; exit 1; fi
fi

IMAGE="vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
EXPECT_DIGEST="sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
# HF_HOME comes from env.sh (written by setup_machine.sh from PILOT_DATA — a user-writable
# dir; /ephemeral top level is root-owned so never default to /ephemeral/$USER directly).
HF_HOME="${HF_HOME:-${PILOT_DATA:-/ephemeral/hr/pilot}/hf}"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EV="staging_evidence/$STAMP"
mkdir -p "$EV"
echo "evidence dir: $EV"

stop () { echo "STOP: $1" | tee -a "$EV/STOP.txt"; exit 1; }

echo "== [0/5] environment record =="
{
  date -u; uname -a
  nvidia-smi || echo "nvidia-smi FAILED — driver not working"
  python3 --version; "$PY" --version; df -h . /ephemeral 2>/dev/null; free -g
  docker info --format 'DockerRootDir={{.DockerRootDir}}' 2>/dev/null || echo "docker info failed (are you in the docker group? no sudo per R2)"
  echo "HF_HOME=$HF_HOME"
  echo "RAPID_API_KEY set: ${RAPID_API_KEY:+yes}${RAPID_API_KEY:-NO (needed for main run, not staging)}"
  if [ -n "${RAPID_API_KEY:-}" ]; then
    if curl -sf -m 15 -o /dev/null \
        -H "X-RapidAPI-Key: $RAPID_API_KEY" -H "X-RapidAPI-Host: forward-reverse-geocoding.p.rapidapi.com" \
        "https://forward-reverse-geocoding.p.rapidapi.com/v1/search?q=Paris"; then
      echo "RAPID_API_KEY probe: PASS (value not recorded)"
    else
      echo "RAPID_API_KEY probe: FAIL (key present but call failed) — must pass before main run"
    fi
  fi
} > "$EV/env.txt" 2>&1
cat "$EV/env.txt"

echo "== [0b/5] docker storage free-space pre-flight (vLLM image needs ~20G) =="
# The containerd snapshotter writes image layers under /var/lib/containerd, NOT
# necessarily DockerRootDir — so check the filesystem that actually holds it.
STOR_PATH=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo "")
for cand in "$STOR_PATH" /var/lib/containerd /var/lib/docker; do
  [ -n "$cand" ] || continue
  if df_out=$(df --output=avail "$cand" 2>/dev/null | tail -1); then
    free_g=$(( df_out / 1024 / 1024 ))
    echo "  $cand -> ${free_g}G free"
    if [ "$free_g" -lt 40 ]; then
      echo "STOP: docker storage path $cand has only ${free_g}G free (<40G). The vLLM image (~20G) won't fit."
      echo "  No-sudo fix (R2): run staging against a ROOTLESS docker with data on a user-writable dir:"
      echo "    conda install -c conda-forge docker-cli rootlesskit slirp4netns fuse-overlayfs -y"
      echo "    export PILOT_DATA=${PILOT_DATA:-/ephemeral/hr/pilot}   # must be user-writable"
      echo "    mkdir -p \"\$PILOT_DATA/docker-rootless\""
      echo "    export DOCKER_HOST=unix:///run/user/\$(id -u)/docker.sock"
      echo "    rootlesskit --net=slirp4netns dockerd-rootless.sh --data-root \"\$PILOT_DATA/docker-rootless\" --host unix:///run/user/\$(id -u)/docker.sock &"
      echo "  Then re-run with DOCKER_HOST set. (Or ask your admin to point dockerd data-root at a writable dir.)"
      exit 1
    fi
    break
  fi
done

echo "== [1/5] pull pinned vLLM image and verify digest =="
docker pull "$IMAGE" | tee "$EV/docker_pull.log" || stop "docker pull failed"
ACTUAL=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE" | sed 's/.*@//')
{ echo "expected=$EXPECT_DIGEST"; echo "actual=$ACTUAL"; } | tee "$EV/digest_check.txt"
[ "$ACTUAL" = "$EXPECT_DIGEST" ] || stop "container digest mismatch"

echo "== [2/5] CUDA compat probe: nvidia-smi INSIDE the container (1 GPU) =="
# Driver is 570.195.03 (CUDA 12.8); image user-space is CUDA 13.0.2 — must verify
# the container actually sees the GPU before any weight download/launch.
docker run --rm --gpus '"device=0"' "$IMAGE" nvidia-smi \
  | tee "$EV/container_nvidia_smi.txt" \
  || stop "CUDA/driver mismatch — container cannot see GPU. Report back; options: cuda-compat or re-pin image (lock change)."

echo "== [3/5] verify weights against configs/weight_sha256.lock =="
"$PY" tools/hash_weights.py --root "$HF_HOME" --out "$EV/weight_hash_verify.yaml" \
  || stop "weight hash verification failed — do NOT proceed, see $EV/weight_hash_verify.yaml"

echo "== [4/5] per-model launch smoke + peak memory + probes (1 GPU each) =="
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
  echo "--- $key ($model) on port $PORT, GPU 0 only"
  docker run -d --rm --name "staging_$key" --gpus '"device=0"' \
    -v "$HF_HOME:/root/.cache/huggingface" \
    -p "$PORT:8000" \
    -e CUDA_VISIBLE_DEVICES=0 \
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
    mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
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
  mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  [ "$mem" -gt "$peak" ] && peak=$mem
  echo "$key peak_mib=$peak" | tee -a "$EV/peak_memory.txt"
  docker stop "staging_$key" > /dev/null
  PORT=$((PORT+1))
done

echo "== [5/5] bundle =="
BUNDLE="staging_evidence_$STAMP.tar.gz"
tar czf "$BUNDLE" -C staging_evidence "$STAMP"
echo
echo "STAGING DONE — upload this file back to the chat:  $BUNDLE"
[ -f "$EV/STOP.txt" ] && exit 1 || exit 0
