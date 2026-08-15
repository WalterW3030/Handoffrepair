# H100 Staging-Smoke Run Sheet — FOR ADVISOR APPROVAL (not executed)

**Purpose:** produce only the staging-derived values the frozen bundle still needs, with a hard
GPU-hour cap and automatic stop conditions. **This is not the main pilot.** No main-allocation
GPU-hours are consumed; the 35–40 h request stays unapproved until this smoke is reviewed.

## Scope (tightly bounded)

Produce: launch logs for every model, nvidia-smi/driver info, container digest, exact model
revisions + per-file hashes, a tool-call round trip per model, measured tokens/sec and
seconds/episode, peak memory, and the regenerated **measured** manifest. Nothing else runs.

## Hard caps & automatic stop conditions

| Control | Value | Auto-stop condition |
|---|---|---|
| GPU-hour cap | **≤ 6.0 GPU-h** (hard) | script aborts if wall-clock GPU time exceeds 6 h |
| Per-model launch timeout | 15 min | abort model if not serving within 15 min |
| Tool-call round-trip timeout | 5 min/model | record failure, move to next model |
| Calibration episodes | exactly 10 per pair (timed) | stop after 10; no extension |
| Failure policy | any launch failure → record + skip, never retry-loop | no unbounded retries |

## Exact commands

```bash
# 0. environment record (no GPU compute)
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python -c "import torch,sys;print('torch',torch.__version__,'cuda',torch.version.cuda)"
docker inspect --format='{{index .RepoDigests 0}}' <vllm-image>   # container digest -> models.yaml

# 1. weight staging + per-file hashes (~275GB, network-bound; GPU idle)
for m in Qwen/Qwen3-32B Qwen/Qwen3-8B RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic google/gemma-4-31b-it; do
  huggingface-cli download "$m" --revision <pinned-commit>
done
python tools/hash_weights.py --out configs/models.yaml   # per-file SHA-256 manifest

# 2. per-model launch smoke + tool-call round trip + peak memory (serial; one server at a time)
for s in serve_qwen3_8b serve_qwen3_32b serve_llama33_70b serve_gemma4_31b; do
  bash serving/$s.sh & SERVER=$!
  python tools/launch_smoke.py --timeout 900 --capture-nvidia-smi --tool-call-roundtrip
  kill $SERVER
done

# 3. measured calibration (10 timed episodes/pair)
python src/run_pilot.py --phase calibrate --episodes 10   # writes logs/measured_rates.json
python src/run_pilot.py --phase main --from-measured       # regenerates measured manifest

# 4. stop
python tools/budget_check.py --cap 6.0                     # aborts if over cap
```

## Expected duration

Weight download 1–2 h (network, GPU idle) + 4 model launches (~20 min) + round trips (~10 min) +
10-episode calibration (~15 min) ≈ **2–3 h wall-clock, ≤ 1 GPU-h of actual compute** — well inside
the 6 GPU-h hard cap.

## Outputs (all committed, then a new immutable tag)

- `logs/launch_smoke/*.log` (per-model launch + round trip + peak memory + nvidia-smi)
- `configs/models.yaml` filled: per-file hashes, pinned revisions, container digest, vLLM version
- `configs/episodes_pilot.yaml` (from the pinned selector)
- `logs/measured_rates.json` + regenerated measured manifest
- After these, a NEW immutable tag (the current `pilot-freeze-v1` is archived, not moved).
