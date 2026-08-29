#!/usr/bin/env bash
# staging_collect.sh — run the approved M1 staging (run sheet §0-§3) and pack
# all evidence into one tarball to upload back for verification.
# Auto-STOPs (exit 1) on: container digest mismatch, CUDA/driver mismatch,
# weight hash mismatch, server crash, or health timeout.
# Rules: R2 no sudo · R3 exactly 1 GPU (freest GPU auto-selected, overridable via GPU_ID).
# Run from the repo root after setup_machine.sh.
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f env.sh ] && source env.sh
# Rule R3: exactly one GPU — selected below by free memory (GPU_ID), NOT hardcoded to device 0 (shared machine).
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
# Token is NEVER stored on disk or in git (user decision 2026-08-28): if unset or
# polluted, prompt interactively (read -s, no echo). Lives only in this process env.
hf_token_clean() { [ -n "${HF_TOKEN:-}" ] && ! printf '%s' "$HF_TOKEN" | LC_ALL=C grep -qP '[^\x00-\x7F]'; }
if ! hf_token_clean; then
  if [ -n "${HF_TOKEN:-}" ]; then
    echo "HF_TOKEN is set but contains NON-ASCII characters (CJK/full-width from copy-paste) —"
    echo "vLLM would crash with UnicodeEncodeError in the Authorization header."
  else
    echo "HF_TOKEN not set. gemma-4-31b is GATED — a valid token is required."
  fi
  if [ -t 0 ]; then
    tries=0
    until hf_token_clean; do
      tries=$((tries+1)); [ "$tries" -le 3 ] || stop "HF_TOKEN still invalid after 3 attempts."
      read -rsp "Enter HF_TOKEN (input hidden): " HF_TOKEN; echo
      export HF_TOKEN
      hf_token_clean || echo "  rejected: empty or contains non-ASCII chars — re-enter carefully."
    done
  else
    stop "HF_TOKEN missing/invalid and no TTY to prompt. Run: export HF_TOKEN=hf_... (clean ASCII) then re-run."
  fi
fi
echo "HF_TOKEN is set and ASCII-clean (value not recorded)."

echo "== [3/5] verify weights against configs/weight_sha256.lock =="
"$PY" tools/hash_weights.py --root "$HF_HOME" --out "$EV/weight_hash_verify.yaml" \
  || stop "weight hash verification failed — do NOT proceed, see $EV/weight_hash_verify.yaml"

echo "== [4/5] per-model launch smoke + peak memory + probes (1 GPU each) =="
KEYS=(qwen3-32b qwen3-8b qwen3-30b-a3b gemma4-31b)
declare -A MODELS=(
  [qwen3-32b]="Qwen/Qwen3-32B"
  [qwen3-8b]="Qwen/Qwen3-8B"
  # 2026-08-28: pair-2 large slot = Qwen3-30B-A3B-Instruct-2507 (MoE 3.3B active),
  # replacing Llama-3.3-70B-FP8 which could not fit one 79.19 GiB card with
  # R12 headroom at a valid context length (KV ValueError at 8192).
  [qwen3-30b-a3b]="Qwen/Qwen3-30B-A3B-Instruct-2507"
  [gemma4-31b]="google/gemma-4-31B-it"
)

# GPU selection (R3: exactly ONE GPU, but NOT necessarily device 0 — this is a
# shared 8-GPU machine; 2026-08-28 evidence: another process held ~33 GiB on
# cuda:0, causing ValueError "free memory < desired utilization" at startup).
# Pick the GPU with the most FREE memory unless GPU_ID is pinned by the user.
pick_gpu() {
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits \
    | sort -t, -k2 -n | head -1 | awk -F, '{gsub(/ /,"",$1); print $1}'
}
GPU_ID="${GPU_ID:-$(pick_gpu)}"
FREE_MIB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$GPU_ID" | head -1)
echo "selected GPU $GPU_ID (free ${FREE_MIB} MiB; override with GPU_ID=n)"
# Pre-flight: refuse to launch if the chosen GPU can't satisfy 0.90 util of a ~79 GiB card.
[ "$FREE_MIB" -ge 73000 ] || stop "GPU $GPU_ID has only ${FREE_MIB} MiB free (<73 GiB needed for gpu-memory-utilization 0.90). Another tenant/process is on it — check nvidia-smi, pick another GPU_ID, or wait."

PORT=18080
: > "$EV/peak_memory.txt"
mkdir -p "$EV/cids"
for key in "${KEYS[@]}"; do
  model="${MODELS[$key]}"
  echo "--- $key ($model) on port $PORT, GPU $GPU_ID only"
  # NOTE: no --rm. A dead container with --rm is auto-removed, losing its logs.
  # Use --cidfile + explicit capture + `docker rm` after, so we keep the real error.
  # Remove any stale container of this name first: a previous STOP aborts before
  # the cleanup at the end, leaving the dead container holding the name.
  docker rm -f "staging_$key" > /dev/null 2>&1 || true
  cidfile="$EV/cids/$key"
  # --ipc=host is REQUIRED by the vLLM OpenAI image (PyTorch uses shared memory
  # for worker IPC). --gpus device=$GPU_ID alone isolates to that one GPU; do
  # NOT also set CUDA_VISIBLE_DEVICES (can confuse device mapping).
  docker run -d --cidfile "$cidfile" --name "staging_$key" --gpus "\"device=$GPU_ID\"" \
    --ipc=host \
    -e VLLM_ENABLE_CUDA_COMPATIBILITY=1 \
    -v "$HF_HOME:/root/.cache/huggingface" \
    -p "$PORT:8000" \
    ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
    "$IMAGE" \
    "$model" --served-model-name "$key" \
    --max-model-len 24576 --gpu-memory-utilization 0.90 --enforce-eager \
    > /dev/null || stop "docker run failed for $key"

  # Always capture logs + exit code + OOMKilled, even if the container dies
  # before the first poll — this is what finally reveals the REAL cause.
  capture_diag() {
    docker logs "staging_$key" > "$EV/serve_${key}.log" 2>&1 || true
    { echo "exit_code=$(docker inspect -f '{{.State.ExitCode}}' "staging_$key" 2>/dev/null)";
      echo "oom_killed=$(docker inspect -f '{{.State.OOMKilled}}' "staging_$key" 2>/dev/null)";
      echo "error=$(docker inspect -f '{{.State.Error}}' "staging_$key" 2>/dev/null)"; } \
      > "$EV/diag_${key}.txt" 2>/dev/null || true
  }

  ready=0; peak=0
  for _ in $(seq 1 180); do   # up to 30 min
    sleep 10
    if ! docker ps --format '{{.Names}}' | grep -qx "staging_$key"; then
      capture_diag
      # distinguish HF-auth failure from a real crash for an accurate STOP.
      # 2026-08-28 fix: do NOT match bare "token" — it appears inside unrelated
      # errors (e.g. the KV-cache ValueError mentions "tokens") and once caused
      # a false "HF auth failed" STOP for llama33-70b-fp8's real memory error.
      if grep -qiE "authentication error|unauthorized|401 client|403 client|gated repo|access to model|invalid token|token is invalid" "$EV/serve_${key}.log"; then
        stop "HF auth failed serving $key — see $EV/serve_${key}.log. Likely: HF_TOKEN unset/invalid, or the gated gemma-4 license not accepted for this token's account."
      fi
      stop "server died for $key — see $EV/serve_${key}.log and $EV/diag_${key}.txt (exit_code/oom_killed)"
    fi
    mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU_ID")
    [ "$mem" -gt "$peak" ] && peak=$mem
    if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then ready=1; break; fi
  done
  capture_diag
  [ "$ready" = 1 ] || stop "health timeout (30 min) for $key — see $EV/serve_${key}.log and $EV/diag_${key}.txt"

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
  mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU_ID")
  [ "$mem" -gt "$peak" ] && peak=$mem
  echo "$key peak_mib=$peak" | tee -a "$EV/peak_memory.txt"
  docker stop "staging_$key" > /dev/null 2>&1 || true
  docker logs "staging_$key" >> "$EV/serve_${key}.log" 2>&1 || true
  docker rm -f "staging_$key" > /dev/null 2>&1 || true   # cleanup (no --rm, so remove explicitly)
  PORT=$((PORT+1))
done

echo "== [5/5] bundle =="
BUNDLE="staging_evidence_$STAMP.tar.gz"
tar czf "$BUNDLE" -C staging_evidence "$STAMP"
echo
echo "STAGING DONE — upload this file back to the chat:  $BUNDLE"
[ -f "$EV/STOP.txt" ] && exit 1 || exit 0
