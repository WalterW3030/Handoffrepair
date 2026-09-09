# Day 1+ Plan — Post-Validation (2026-09-08, GO accepted by user)

**Basis:** all validation gates closed on 2026-09-08 — T1 4/4 needle FOUND @15.6k tok,
T2 4/4 extraction PASS (0 shim_failures; 3 capability errors logged, not gated),
T3 4/4 serve at frozen settings (headroom caveat M19b recorded), T4 partial (speed
ratios measured: 30b-a3b fastest, 8b ≈ 3.8× 32b, gemma4 slowest ≈1.6× below 32b;
absolute cost NOT measurable from the probe — 13–16 GPU-h remains the planning
estimate, with a Day-1 measured checkpoint as the control).

## Day 1 — build the GPU run path (DONE 2026-09-08) + gates

**M28 found at runbook time:** the runner's gpu mode never called models — mock policy
hardcoded. Fixed this day: `src/gpu_policy.py` + `src/live_client.py` + dry_run gpu
branch + run_pilot wiring (`--pairs`, `--limit`, per-run endpoint pre-flight) +
`configs/decoding.yaml` vllm_endpoints. Mock path untouched.

1. ~~Wire model-backed policy~~ DONE. Pending on-machine: mock regression smoke.
2. **Live dry-run gate (M28):** `tools/gpu_dryrun_gate.sh pair1_32to8` — one real b0
   episode; asserts served names + nonzero usage + ≥1 tool_call. Must PASS before any
   main-run segment.
3. Manifest reality (corrected): **1,180 runs** = 20 episodes × 13 cells (B0 + 4
   columns × 3 switch points) × 2 pairs × 2 seeds + 20 × 7 × 1 held-out. Planning
   estimate 19.72 GPU-h vs 20.0 cap — thin; measured-rate checkpoint governs.

## Day 2 — main run, calibrated pairs + cost calibration

1. Serve pair_1 (qwen3-32b :8000 + qwen3-8b :8001, sim shares 8b) →
   `run_pilot.py --phase main --mode gpu --pairs pair1_32to8` (520 runs).
2. **CHECKPOINT (mandatory):** measured sec/run from pilot_runs.jsonl → re-estimate
   remaining GPU-h → agent reports, user confirms continue/stop/trim.
3. Serve pair_2 (30b :8002 + 8b :8001) → `--pairs pair2_30to8` (520 runs).
4. Push run logs; agent verifies same-day.

## Day 3 — held-out + freeze

5. Serve held-out (32b :8000 + gemma4 :8003 + 8b sim :8001) →
   `--pairs heldout_32to31` (140 runs).
6. Full evidence push; results table assembled.
7. RC tag `pilot-rc-v1` candidate — ONLY after user confirms results sane.
   `pilot-freeze-v1` never touched.

## Day 4 — buffer

Absorbs overruns from the ranked risks; otherwise complete at Day 3.

## Ranked risks (accepted at GO)

1. **Shared-machine memory preemption** (high likelihood — happened 3× in staging):
   peaks at 93–95% card; neighbor grabbing memory kills a run mid-day. Mitigations:
   ≥73 GiB pre-flight; per-episode logging loses only the in-flight episode; restart
   from checkpoint.
2. **gemma4 latency** (medium): inflates Day-2 cost; bounded — Day 2 is the short day.
3. **Capability-error clustering** (medium): real-episode tool-choice errors appear as
   data (by design); calibrated-pair comparison absorbs model-level differences.
4. **Cost above 16 GPU-h** (medium): controlled by the Day-1 step-2 checkpoint.

## Known housekeeping

- Untracked strays on the machine repo root: `staging_run.log` (old Aug-28 staging
  output), `quick_probe_out/` — decide clean vs .gitignore at next maintenance window.
- GitHub PAT: revoke after the final RC tag push.
