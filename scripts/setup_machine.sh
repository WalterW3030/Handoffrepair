#!/usr/bin/env bash
# setup_machine.sh — one-time host setup for the HandoffRepair pilot.
# Run on the GPU machine from the repo root. Idempotent; safe to re-run.
# Requires: HF_TOKEN env var (HuggingFace access token).
set -euo pipefail
cd "$(dirname "$0")/.."

: "${HF_TOKEN:?Set HF_TOKEN first:  export HF_TOKEN=hf_...}"

TS_COMMIT=165848b9a78cead7ca7fe7c89c688b58e6501219

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

echo "== [3/5] host python deps (pinned) =="
pip install \
  openai==1.17.0 \
  pydantic==2.7.4 \
  pydantic-core==2.18.2 \
  polars==0.20.31 \
  phonenumbers pycountry geopy geographiclib holidays pint \
  tqdm pyyaml \
  "huggingface_hub[cli]"

cat > env.sh <<'EOF'
# source this before any pilot command
export TOOLSANDBOX_REPO="$(pwd)/ToolSandbox"
export PYTHONPATH="$(pwd)/ToolSandbox:${PYTHONPATH:-}"
EOF
# shellcheck disable=SC1091
source env.sh

echo "== [4/5] model weights @ pinned revisions (~230GB total) =="
dl () {  # dl <repo_id> <revision>
  echo "--- $1 @ $2"
  hf download "$1" --revision "$2" \
    || huggingface-cli download "$1" --revision "$2"
}
dl "Qwen/Qwen3-32B"                                9216db576d6d8c4ab54e1d1db01f5b45fdcbfb92
dl "Qwen/Qwen3-8B"                                 b968826d9c46dd6066d109eabc25cc8de14886c7
dl "RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic"   f50dbad2708ecafd3bd1f17a8a15c265487a1b60
dl "google/gemma-4-31B-it"                         842da3798ffed395c23e61f27e096c6b8d7ea904

echo "== [5/5] verify all 39 weight files against lock =="
python tools/hash_weights.py --out weight_hash_verify.yaml

echo
echo "SETUP OK. Next: bash scripts/staging_collect.sh"
