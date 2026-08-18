# Day 0 Record 7 — Advisor Requirement Status

**As of:** 2026-08-17, HEAD `075e7a8` (pushed). Tag `pilot-freeze-v1` archived at `bbe8030`, untouched. No GPU run started.

## Status of every instructor (advisor) requirement

| # | Advisor requirement | Status | Evidence (file in repo) |
|---|---|---|---|
| 1 | New immutable RC tag with **no CPU-resolvable TBDs** | ✅ CPU-resolvable part done / ⛔ tag blocked | `configs/models.yaml` (zero TBDs), `configs/episodes_pilot.yaml` (78 kept/4 excluded), `configs/weight_sha256.lock` (39 files), `serving.container_image` digest pinned. New tag cut only AFTER staging evidence; pilot-freeze-v1 stays archived |
| 2 | Clean-environment verification command + dependency lock / container digest | ✅ Done | `VERIFY.md`, `requirements-lock.txt`, fresh-clone test 13/13 → now 18/18 with ToolSandbox |
| 3 | Discoverable test output | ✅ Done | `tests/test_pilot.py`, `tests/test_scorer.py`, `tests/test_toolsandbox_dryrun.py` — 18/18 pass |
| 4 | One real ToolSandbox dry-run through every implemented column | ✅ Done | `logs/toolsandbox_dry_run.json`: B0/B1/B2a/B3/compiler similarity 1.000, A1 prefix identity PASS, A2 world identity PASS, info-loss discrimination confirmed. Code: `src/toolsandbox/dry_run.py`, `src/toolsandbox/executor.py` |
| 5 | Unique-run manifest + reconciled budget | ✅ Done | `logs/run_manifest.json`: 1,180 unique runs, 0 dupes, 0 B0-with-switch rows, 19.72 GPU-h ≤ 20.0 cap, planning/measured separated. Source: `configs/sizing.yaml` |
| 6 | Bounded H100 staging-smoke run sheet | ✅ Written / ⛔ execution blocked (needs advisor approval) | `staging_smoke_runsheet.md`: 6 GPU-h hard cap, auto-stops, digest must-match → STOP |
| — | Do not move tag pilot-freeze-v1 | ✅ Honored | tag at `bbe8030`, unchanged |
| — | Do not execute staging smoke until approved | ✅ Honored | not executed |

**Remaining work is all staging-derived:** H100 launch logs + peak-memory for 4 models,
measured GPU rates (`gpu_measured`), Gemma-4 20-probe gate → then new RC tag → then main run
(1,180 runs + 150 B6 rollouts).

## Supporting files (all in github.com/WalterW3030/Handoffrepair @ `075e7a8`)

| File | Role |
|---|---|
| `staging_smoke_runsheet.md` | The bounded staging plan — send to advisor for approval |
| `configs/models.yaml` | Pinned checkpoints/revisions + container digest + gemma probe gate |
| `configs/weight_sha256.lock` | 39 per-file weight hashes for offline verification |
| `configs/sizing.yaml` | Single source of truth for enumeration & budget |
| `configs/episodes_pilot.yaml` | 78 kept scenario names (pinned commit `165848b9`) |
| `VERIFY.md` | One-command clean-environment verification incl. dry-run |
| `logs/toolsandbox_dry_run.json` | Dry-run evidence (A1/A2 PASS, 5 columns 1.000) |
| `logs/run_manifest.json` | Enumerated 1,180-run manifest |
| `logs/pilot_runs.jsonl` / `logs/analysis.json` | 33-run cell-coverage smoke + Q1–Q4 machinery output |
| `src/run_pilot.py` | Executable phases: calibrate / main / b6 / analyze |
| `src/toolsandbox/dry_run.py` + `executor.py` | Real ToolSandbox dry-run driver + world adapter |
| `tests/` | 18 tests, discoverable output |
| `requirements-lock.txt` | Python dependency lock |
