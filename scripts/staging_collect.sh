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
# If env.sh carries a stale HF_HOME outside PILOT_DATA, derive from PILOT_DATA instead.
PILOT_DATA="${PILOT_DATA:-/ephemeral/hr/pilot}"
if [ -n "${HF_HOME:-}" ] && [ "${HF_HOME#"$PILOT_DATA"}" = "$HF_HOME" ]; then
  echo "NOTE: ignoring stale HF_HOME=$HF_HOME (not under PILOT_DATA); deriving from PILOT_DATA."
  HF_HOME="$PILOT_DATA/hf"
fi
HF_HOME="${HF_HOME:-$PILOT_DATA/hf}"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EV="staging_evidence/$STAMP"
mkdir -p "$EV"
echo "evidence dir: $EV"

stop () { echo "STOP: $1" | tee -a "$EV/STOP.txt"; exit 1; }

echo "== [-1/5] docker daemon reachable? =="
DOCKER_MODE="${DOCKER_MODE:-system}"
if ! docker info >/dev/null 2>&1; then
  if [ "$DOCKER_MODE" = rootless ]; then
    echo "STOP: cannot reach ROOTLESS docker daemon (DOCKER_HOST=${DOCKER_HOST:-unset})."
    echo "  Start it ONCE, persistent:"
    echo "    mkdir -p /ephemeral/hr/pilot/docker-rootless /ephemeral/hr/pilot/logs"
    echo "    setsid bash -c 'rootlesskit --net=slirp4netns dockerd-rootless.sh --data-root /ephemeral/hr/pilot/docker-rootless --host unix:///run/user/\$(id -u)/docker.sock' > /ephemeral/hr/pilot/logs/dockerd.log 2>&1 < /dev/null &"
    echo "    sleep 8 && docker info --format '{{.DockerRootDir}}'"
  else
    echo "STOP: cannot reach SYSTEM docker (default socket). You're in the docker group, so:"
    echo "  - if you relocated storage: sudo systemctl restart docker  (reported sudo use)"
    echo "  - check: ls -l /var/run/docker.sock ; docker version"
    echo "  - to use rootless instead: export DOCKER_MODE=rootless && source env.sh"
  fi
  exit 1
fi
echo "docker OK (mode=$DOCKER_MODE): $(docker info --format '{{.DockerRootDir}}')"

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
# Docker 29 defaults to the CONTAINERD image store: image layers go to
# /var/lib/containerd (NOT moved by daemon.json data-root). We require images under the
# big disk. Detect the snapshotter; if containerd store is active, require its path off /.
SNAP=$(docker info --format '{{.DriverStatus}}' 2>/dev/null || echo "")
echo "  docker DriverStatus: $SNAP"
if echo "$SNAP" | grep -q "io.containerd.snapshotter"; then
  echo "STOP: Docker is using the CONTAINERD image store (Docker 29 default) — image layers"
  echo "  go to /var/lib/containerd on the root disk (2G free), and daemon.json data-root does"
  echo "  NOT move them. Fix (you run, sudo — reported per R2):"
  echo '    echo -e "{\n  \"data-root\": \"/ephemeral/hr/docker-data\",\n  \"features\": {\"containerd-snapshotter\": false}\n}" | sudo tee /etc/docker/daemon.json'
  echo "    sudo systemctl restart docker"
  echo "  Then verify:  docker info --format '{{.DriverStatus}}'  (should NOT mention containerd)"
  exit 1
fi
# overlay2/classic store: images live under DockerRootDir — check its free space.
STOR_PATH=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo "")
echo "  DockerRootDir=$STOR_PATH"
if [ -n "$STOR_PATH" ]; then
  free_kb=$(df --output=avail "$STOR_PATH" 2>/dev/null | tail -1 || echo 0)
  free_g=$(( free_kb / 1024 / 1024 ))
  echo "  ${STOR_PATH} -> ${free_g}G free"
  if [ "$free_g" -lt 40 ]; then
    echo "STOP: docker image storage $STOR_PATH has only ${free_g}G free (<40G) — vLLM image (~20G) won't fit."
    echo "  Point data-root at /ephemeral/hr/docker-data in /etc/docker/daemon.json (sudo, reported) and restart docker."
    exit 1
  fi
fi

echo "== [1/5] pull pinned vLLM image and verify digest =="
docker pull "$IMAGE" | tee "$EV/docker_pull.log" || stop "docker pull failed"
ACTUAL=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE" | sed 's/.*@//')
{ echo "expected=$EXPECT_DIGEST"; echo "actual=$ACTUAL"; } | tee "$EV/digest_check.txt"
[ "$ACTUAL" = "$EXPECT_DIGEST" ] || stop "container digest mismatch"

echo "== [2/5] CUDA compat probe: nvidia-smi INSIDE the container (1 GPU) =="
# Driver is 570.195.03 (CUDA 12.8); image user-space is CUDA 13.0.2 — must verify
# the container actually sees the GPU before any weight download/launch.
# NOTE: this image's default ENTRYPOINT is `vllm serve`, so a bare `docker run IMAGE nvidia-smi`
# makes vLLM treat "nvidia-smi" as a MODEL (→ 401 download error). Must override the entrypoint.
docker run --rm --gpus '"device=0"' --entrypoint nvidia-smi "$IMAGE" \
  | tee "$EV/container_nvidia_smi.txt" \
  || stop "CUDA/driver mismatch — container cannot see GPU. Report back; options: cuda-compat or re-pin image (lock change)."

echo "== [2b/5] HF token pre-check (vLLM pulls models from HF at serve time) =="
if [ -z "${HF_TOKEN:-}" ]; then
  stop "HF_TOKEN not set in this shell. vLLM containers download models from HF and need it.
  Fix:  export HF_TOKEN=hf_...   (then re-run). gemma-4-31b is GATED — the token's account must have accepted its license."
else
  echo "HF_TOKEN is set (value not recorded)."
fi

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
      # distinguish HF-auth failure from a real crash for an accurate STOP
      if grep -qiE "authentication|unauthorized|401|403|gated|token" "$EV/serve_${key}.log"; then
        stop "HF auth failed serving $key — see $EV/serve_${key}.log. Likely: HF_TOKEN unset/invalid, or the gated gemma-4 license not accepted for this token's account."
      fi
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
