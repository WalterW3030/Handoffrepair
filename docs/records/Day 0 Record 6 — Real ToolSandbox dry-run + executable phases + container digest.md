# Day 0 Record 6 — Real ToolSandbox dry-run, executable run_pilot phases, container digest pin

**Status:** Day 0 (pilot NOT started; no GPU used). Commits `c638acd` → `183152d` → `075e7a8`, pushed to github.com/WalterW3030/Handoffrepair. Tag `pilot-freeze-v1` untouched at `bbe8030` (archived RC per advisor).

## Trigger

User instruction: with the implemented protocols (self_flight gate), re-check the advisor's
latest letter; (1) list what can be done, (2) finish everything doable, checking tasks one by one.

## Pre-flight (self_flight)

- `self_flight.py --check` with task declaration quoting the instruction: 9/9 checks PASS, gate
  START_ALLOWED, hash-chained log appended (records 10+). Tamper test previously verified
  (LOG_CHAIN_BROKEN on edit).

## What was found broken (honest baseline)

1. **run_pilot.py was still stub-phased at HEAD**: `calibrate`/`b6`/`analyze` only printed
   messages; `main` only enumerated; episodes were `ep_{i:03d}` placeholders; it called
   `manifest.enumerate_runs` with an outdated 5-arg signature (would have crashed).
2. **executor.py was a stub**: returned an empty world_impl and referenced
   `ToolBackend.HERMES`, which does not exist at the pinned ToolSandbox commit.
3. These meant advisor item 2 ("one fresh-clone command executes the complete path") was NOT
   actually satisfied despite earlier records claiming it. Recorded as process issue #11
   (premature completion) — now corrected with executable evidence.

## T-d — Real ToolSandbox dry-run through every implemented column

New `src/toolsandbox/dry_run.py` + rewritten `src/toolsandbox/executor.py`:

- Loads the pinned ToolSandbox checkout (`165848b9`), all 78 kept scenarios importable with
  pinned deps (polars==0.20.31 etc.).
- Runs scenario `add_reminder_content_and_date_and_time` through **B0, B1, B2a, B3, compiler**
  with real tool execution via ToolSandbox's own `ExecutionEnvironment` role (agent messages
  are Python source executed in the REPL; tool_trace rows land in SANDBOX).
- Frozen harness semantics preserved: fresh `ExecutionContext` per run, `IdempotencyLedger`
  (pre-execution suppression, stable logical-op IDs), `prefix_ids["switch"]` pairing anchor,
  ε-gate, and the REAL handoff hooks from `src/columns/{b2a,b3}.py` + `src/compiler.py`.
- Deterministic oracle-scripted policy derived from each scenario's own milestones (no LLM);
  every action labelled `handoff_view` vs `gold_fallback` — measures whether the column's
  handoff representation carries the values the target needs.
- Scoring: ToolSandbox's own `scenario.evaluation.evaluate` (milestone/minefield DAG).

**Evidence (`logs/toolsandbox_dry_run.json`):**
- All five columns: similarity **1.000**, minefield 0 (turn counts 4).
- **A1 prefix identity: PASS** — one anchor `cbdf70ecc05d…` across B1/B2a/B3/compiler.
- **A2 world identity: PASS** — final REMINDER DB byte-identical across all five columns
  (single scenario load; only server-generated uuid/creation_timestamp excluded).
- **Discrimination check**: `handoff_info_sufficient` = True for B1, False for B2a/B3/compiler
  at S1 — the harness detects handoff information loss as designed (typed-state/compiler
  payloads drop tool RESULTS; raw transcript keeps them).
- 5 new pytest tests (`tests/test_toolsandbox_dryrun.py`): **18/18 pass** with the checkout
  present; skip cleanly without it.

## run_pilot.py — all four phases now executable (mock mode, CPU)

- `--phase calibrate`: timed real runs (2 episodes × B0/B1 × 3 pairs) →
  `logs/measured_rates.json` labelled `kind=cpu_mock` (GPU accounting must re-measure on H100).
- `--phase main`: manifest regenerated from `configs/sizing.yaml` single source with REAL
  scenario names (no placeholders): **1,180 runs, 19.72 GPU-h planning, within 20h cap**;
  then executes a 33-run cell-coverage smoke (every pair × column × switch point) through the
  real ToolSandbox world, appending to `logs/pilot_runs.jsonl` in the frozen schema.
- `--phase b6`: yardstick accounting path executable (3 mock rollouts logged; full 150 on GPU).
- `--phase analyze`: hierarchical bootstrap CIs + ε-recovery + Q1–Q4 from the append-only log
  → `logs/analysis.json`. Mock verdict honestly uninformative (all scores 1.0 with the oracle
  policy ⇒ no degradation to detect; Q4 passes, restart rate 0).
- `--mode gpu` shares the code path and refuses to start without configured vLLM endpoints.

## T-e — vLLM container pinned by digest (CPU-resolved)

- `configs/models.yaml: serving.container_image` =
  `vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967`
  (v0.27.1; built 2026-08-11; vLLM commit 6e448d0e; CUDA 13.0.2; arch list incl. sm_90/H100).
- Resolved via registry metadata (Docker Hub blocked from sandbox; used mirror index data).
- Staging run sheet updated: `docker pull` by digest and MUST-MATCH check — mismatch ⇒ STOP.
  No staging-derived value remains in configs.

## T-f — Manifest single-source + budget re-verified

- 1,180 runs, 1,180 unique (pair, column, switch_point, episode, seed) keys, 0 duplicates.
- 0 B0-with-switch rows. All 20 episode IDs are real ToolSandbox scenario names.
- 19.72 GPU-h (planning rates) ≤ 20.0 hard cap; measured rates stay separate (`rate_kind`).
- `episodes.yaml`/`seeds.yaml` defer to `sizing.yaml`; `manifest.py` has no hardcoded counts.

## Errors encountered and fixed this round

| # | Error | Fix |
|---|-------|-----|
| 1 | ToolBackend.HERMES absent at pinned commit | `getattr(..., "HERMES", DEFAULT)` |
| 2 | SYSTEM→EXECUTION_ENVIRONMENT init message (tool imports) never executed → NameError | `env.respond(ending_index=i)` for init messages before the episode loop |
| 3 | A2 world divergence: seed DB timestamps derive from wall clock per scenario load | single shared scenario load across columns (documented in load_world docstring) |
| 4 | Generic policy default args (year=0) → ValueError, trace milestone lost | fill datetime-component params from gold milestone timestamp |
| 5 | `manifest.enumerate_runs` called with stub-era signature | rewired to `(sizing, episodes, measured)` |
| 6 | log schema rejected dry-run records (missing gate_branch) | ε-gate now runs in dry-run path, matching runner.run |
| 7 | GitHub push failed: token file wiped with /tmp | re-set remote from conversation-provided PAT, pushed, scrubbed remote config |

## Remaining blocked items (GPU/approval-bound — cannot be done CPU-side)

1. H100 launch evidence + peak-memory report for all four models (needs H100 80GB).
2. Measured runtime/token statistics (`kind=gpu_measured`) — needs GPU calibration run.
3. Gemma-4 probe gate execution (20/20 tool-call parse) — needs the served model.
4. Staging smoke per `staging_smoke_runsheet.md` — **awaiting advisor approval**, not executed.
5. New immutable release-candidate tag — must wait for staging-derived evidence (advisor:
   do not move pilot-freeze-v1).
6. Full 1,180-run manifest execution + 150 B6 rollouts — GPU machine only.
