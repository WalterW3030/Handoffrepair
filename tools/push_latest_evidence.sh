#!/usr/bin/env bash
# push_latest_evidence.sh — auto-find the newest staging_evidence/<ts>/ dir,
# copy all serve/diag/smoke/peak/probe logs into evidence/, commit, push.
# Usage: bash tools/push_latest_evidence.sh [message]
set -euo pipefail
cd "$(dirname "$0")/.."

MSG="${1:-evidence: auto-push $(date -u +%Y%m%dT%H%M%SZ)}"

# newest staging dir
LATEST=$(ls -t staging_evidence/ 2>/dev/null | head -1)
[ -n "$LATEST" ] || { echo "no staging_evidence/* dirs found"; exit 1; }
echo "latest staging dir: $LATEST"

# copy all per-model logs + diagnostics
mkdir -p evidence
copied=0
for f in staging_evidence/"$LATEST"/serve_*.log \
         staging_evidence/"$LATEST"/diag_*.txt \
         staging_evidence/"$LATEST"/smoke_*.json \
         staging_evidence/"$LATEST"/peak_memory.txt \
         staging_evidence/"$LATEST"/gemma4_toolcall_probe.json \
         staging_evidence/"$LATEST"/weight_hash_verify.yaml \
         staging_evidence/"$LATEST"/env.txt \
         staging_evidence/"$LATEST"/STOP.txt; do
  [ -f "$f" ] && cp "$f" evidence/ && copied=$((copied+1))
done
echo "copied $copied files to evidence/"

# pull (remote may have agent commits), commit, push
git pull --no-rebase origin master
git add evidence/
if git diff --cached --quiet; then
  echo "nothing new to commit (evidence already up to date)"
  exit 0
fi
git -c user.name="WalterW3030" -c user.email="walterw3030@users.noreply.github.com" commit -m "$MSG"
git push origin master
echo "pushed: $MSG"
