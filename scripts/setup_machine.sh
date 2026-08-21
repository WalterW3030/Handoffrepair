#!/usr/bin/env bash
# setup_machine.sh — one-time host setup for the HandoffRepair pilot.
# Run on the GPU machine from the repo root. Idempotent; safe to re-run.
# Requires: HF_TOKEN env var (HuggingFace access token).
# Rules: R2 no sudo (nothing here needs it) · R3 single GPU (no GPU use here) ·
#        large storage on a USER-WRITABLE dir (PILOT_DATA; /ephemeral top level is
#        root-owned so we never mkdir there directly — R5).
set -euo pipefail
cd "$(dirname "$0")/.."

: "${HF_TOKEN:?Set HF_TOKEN first:  export HF_TOKEN=hf_...}"

TS_COMMIT=165848b9a78cead7ca7fe7c89c688b58e6501219

echo "== [0/5] pre-flight environment checks =="
python3 --version | tee python_version.txt
# HF cache must NOT land on / (2G free). Base: PILOT_DATA (default on /ephemeral).
# HF cache must NOT land on / (2G free). Default base: PILOT_DATA on /ephemeral, but
# /ephemeral top level is root-owned — so use a USER-WRITABLE dir. Override with:
#   export PILOT_DATA=/some/writable/dir   (then re-run)
PILOT_DATA="${PILOT_DATA:-/ephemeral/$USER/pilot}"
if ! mkdir -p "$PILOT_DATA" 2>/dev/null || [ ! -w "$PILOT_DATA" ]; then
  echo "STOP: cannot create/write PILOT_DATA=$PILOT_DATA (likely /ephemeral is root-owned)."
  echo "  Per R5 I won't touch unpermitted paths. Do ONE of:"
  echo "   a) point me at an existing writable dir:  export PILOT_DATA=<writable_dir> && bash scripts/setup_machine.sh"
  echo "   b) ask your admin (their sudo):            sudo mkdir -p /ephemeral/$USER && sudo chown $USER /ephemeral/$USER"
  echo "  Then re-run. To find a writable dir:  ls -ld /ephemeral/* 2>/dev/null"
  exit 1
fi
export HF_HOME="${HF_HOME:-$PILOT_DATA/hf}"
mkdir -p "$HF_HOME"
FREE_KB=$(df --output=avail "$HF_HOME" | tail -1)
echo "HF_HOME=$HF_HOME  free=$((FREE_KB/1024/1024))G"
[ "$FREE_KB" -lt $((260*1024*1024)) ] && echo "WARNING: <260G free on HF_HOME filesystem — weights need ~230G"
# Docker root dir free space (vLLM image ~20G). No sudo: report only.
ROOTDIR=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo UNKNOWN)
echo "DockerRootDir=$ROOTDIR"
if [ "$ROOTDIR" != UNKNOWN ]; then
  df -h "$ROOTDIR" | tail -1
  FREE_DOCKER_KB=$(df --output=avail "$ROOTDIR" | tail -1)
  [ "$FREE_DOCKER_KB" -lt $((40*1024*1024)) ] && \
    echo "WARNING: <40G free for docker images. No-sudo fix: rootless docker with XDG_DATA_HOME on /ephemeral, or ask admin to relocate."
fi

echo "== [1/5] python env (Rule R4: conda env OR project venv, python 3.10-3.12) =="
if [ -n "${CONDA_PREFIX:-}" ]; then
  echo "conda env detected: $CONDA_PREFIX ($(python --version 2>&1)) — using it, skipping venv creation"
  PYBIN="$(which python)"
else
  echo "no conda env active — creating project venv .venv"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYBIN=.venv/bin/python
fi
PYVER=$("$PYBIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
case "$PYVER" in
  3.10|3.11|3.12) ;;
  *) echo "STOP: python $PYVER — pinned deps have prebuilt wheels only for 3.10-3.12.
       conda fix:  conda create -n handoffrepair python=3.12 -y && conda activate handoffrepair"; exit 1;;
esac
"$PYBIN" -m pip install --upgrade pip
echo "python env: $PYBIN ($PYVER)" | tee python_env.txt

echo "== [2/5] ToolSandbox @ pinned commit =="
if [ ! -d ToolSandbox ]; then
  git clone https://github.com/apple/ToolSandbox.git
fi
git -C ToolSandbox fetch --all --quiet
git -C ToolSandbox checkout "$TS_COMMIT"
git -C ToolSandbox rev-parse HEAD | tee toolsandbox_commit.txt

echo "== [3/5] host python deps (pinned; full list + rationale in docs/ENVIRONMENT.md) =="
"$PYBIN" -m pip install \
  openai==1.17.0 \
  pydantic==2.7.4 \
  pydantic-core==2.18.4 \
  polars==0.20.31 \
  phonenumbers pycountry geopy geographiclib holidays pint \
  flexcache flexparser absl-py distro \
  numpy tqdm pyyaml \
  "huggingface_hub[cli]" \
  pytest==9.1.1

echo "== [3b/5] import smoke test (fails loudly if anything is missing) =="
"$PYBIN" - <<'EOF'
import tool_sandbox  # via PYTHONPATH, pinned commit
import polars, pydantic, openai, numpy, yaml, tqdm
import phonenumbers, pycountry, geopy, geographiclib, holidays, pint
import absl, distro, flexcache, flexparser
assert polars.__version__ == "0.20.31", polars.__version__
assert pydantic.__version__ == "2.7.4", pydantic.__version__
assert openai.__version__ == "1.17.0", openai.__version__
print("IMPORT_SMOKE_OK")
EOF
"$PYBIN" -m pip freeze | tee env_freeze.txt

cat > env.sh <<EOF
# source this before any pilot command
export TOOLSANDBOX_REPO="\$(pwd)/ToolSandbox"
export PYTHONPATH="\$(pwd)/ToolSandbox:\${PYTHONPATH:-}"
export HF_HOME="$HF_HOME"
export CUDA_VISIBLE_DEVICES=0   # Rule R3: exactly 1 GPU, always
export PILOT_PYTHON="$PYBIN"    # Rule R4: this interpreter only
EOF
# shellcheck disable=SC1091
source env.sh

echo "== [4/5] model weights @ pinned revisions (~230GB total, into $HF_HOME) =="
dl () {  # dl <repo_id> <revision>
  echo "--- $1 @ $2"
  hf download "$1" --revision "$2" \
    || huggingface-cli download "$1" --revision "$2"
}
# revisions copied verbatim from configs/weight_sha256.lock (single source of truth)
dl "Qwen/Qwen3-32B"                                9216db5781bf21249d130ec9da846c4624c16137
dl "Qwen/Qwen3-8B"                                 b968826d9c46dd6066d109eabc6255188de91218
dl "RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic"   f50dbad2c84590ca17dc51e207c34321b65ff14b
dl "google/gemma-4-31B-it"                         842da3794eaa0b77d5f08bae87a17459d91ff475

echo "== [5/5] verify all 39 weight files against lock =="
"$PYBIN" tools/hash_weights.py --root "$HF_HOME" --out weight_hash_verify.yaml

echo "== [5b/5] RAPID_API_KEY probe (secret: env var only, never logged/stored) =="
if [ -z "${RAPID_API_KEY:-}" ]; then
  echo "RAPID_API_KEY not set — OK for staging; REQUIRED before the main run (11/78 scenarios call RapidAPI tools)."
  echo "  Set it on this machine only:  echo 'export RAPID_API_KEY=<key>' >> ~/.bashrc"
else
  if curl -sf -m 15 -o /dev/null \
      -H "X-RapidAPI-Key: $RAPID_API_KEY" -H "X-RapidAPI-Host: forward-reverse-geocoding.p.rapidapi.com" \
      "https://forward-reverse-geocoding.p.rapidapi.com/v1/search?q=Paris"; then
    echo "RAPID_API_KEY probe: PASS (value not recorded)"
  else
    echo "RAPID_API_KEY probe: FAIL — key present but API call failed (key invalid, API not subscribed, or host mismatch)."
    echo "  Not blocking setup, but the main run gate will require a passing probe."
  fi
fi

echo
echo "SETUP OK. Next: bash scripts/staging_collect.sh"
