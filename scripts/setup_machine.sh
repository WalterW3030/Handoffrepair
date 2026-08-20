#!/usr/bin/env bash
# setup_machine.sh — one-time host setup for the HandoffRepair pilot.
# Run on the GPU machine from the repo root. Idempotent; safe to re-run.
# Requires: HF_TOKEN env var (HuggingFace access token).
# Rules: R2 no sudo (nothing here needs it) · R3 single GPU (no GPU use here) ·
#        all large storage on /ephemeral (root / has only ~11G free).
set -euo pipefail
cd "$(dirname "$0")/.."

: "${HF_TOKEN:?Set HF_TOKEN first:  export HF_TOKEN=hf_...}"

TS_COMMIT=165848b9a78cead7ca7fe7c89c688b58e6501219

echo "== [0/5] pre-flight environment checks =="
python3 --version | tee python_version.txt
# HF cache must NOT land on / (11G free). Default to /ephemeral.
export HF_HOME="${HF_HOME:-/ephemeral/$USER/hf}"
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

echo "== [1/5] python venv =="
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip

echo "== [2/5] ToolSandbox @ pinned commit =="
if [ ! -d ToolSandbox ]; then
  git clone https://github.com/facebookresearch/ToolSandbox.git
fi
git -C ToolSandbox fetch --all --quiet
git -C ToolSandbox checkout "$TS_COMMIT"
git -C ToolSandbox rev-parse HEAD | tee toolsandbox_commit.txt

echo "== [3/5] host python deps (pinned; full list + rationale in docs/ENVIRONMENT.md) =="
pip install \
  openai==1.17.0 \
  pydantic==2.7.4 \
  pydantic-core==2.18.2 \
  polars==0.20.31 \
  phonenumbers pycountry geopy geographiclib holidays pint \
  flexcache flexparser absl-py distro \
  numpy tqdm pyyaml \
  "huggingface_hub[cli]" \
  pytest==9.1.1

echo "== [3b/5] import smoke test (fails loudly if anything is missing) =="
python - <<'EOF'
import tool_sandbox  # via PYTHONPATH, pinned commit
import polars, pydantic, openai, numpy, yaml, tqdm
import phonenumbers, pycountry, geopy, geographiclib, holidays, pint
import absl, distro, flexcache, flexparser
assert polars.__version__ == "0.20.31", polars.__version__
assert pydantic.__version__ == "2.7.4", pydantic.__version__
assert openai.__version__ == "1.17.0", openai.__version__
print("IMPORT_SMOKE_OK")
EOF
pip freeze | tee env_freeze.txt

cat > env.sh <<EOF
# source this before any pilot command
export TOOLSANDBOX_REPO="\$(pwd)/ToolSandbox"
export PYTHONPATH="\$(pwd)/ToolSandbox:\${PYTHONPATH:-}"
export HF_HOME="$HF_HOME"
export CUDA_VISIBLE_DEVICES=0   # Rule R3: exactly 1 GPU, always
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
python tools/hash_weights.py --root "$HF_HOME" --out weight_hash_verify.yaml

echo
echo "SETUP OK. Next: bash scripts/staging_collect.sh"
