# Day 0 Record 9 — Autonomous Pass (2026-08-18)

**HEAD:** `410026e` (pushed). Tag `pilot-freeze-v1` untouched. No GPU used. No machine exists yet.

## Instruction

Move weight pre-download to on-machine; do everything doable without machine/human help; list the rest.

## Done autonomously (this pass)

| # | Item | Evidence |
|---|---|---|
| 1 | Weight download + digest pull moved into Phase B (on-machine) | `Pending Items — Logical Order + Steps.md` updated (A1/A2 removed; B1/B2 carry them) |
| 2 | **A3 mock full-manifest soak**: 1,180/1,180 runs through the real ToolSandbox worlds | `logs/pilot_runs.jsonl` + `logs/mock_soak_report.json` |
| 3 | Soak-caught defect fixed: strict-pairing prefix anchors broke across columns (wall-clock timestamps + server uuid4 inside tool results) | `mock_now` frozen per-(episode,seed) clock + deterministic uuid4 in dry_run.py → **300 pairing groups, 0 violations** |
| 4 | Policy fixes: gold milestone trace args; valid datetime/coordinate/string param filling; RapidAPI network tools detected by source inspection and skipped; exception path labelled gold_fallback; info-sufficiency judged on float fields only | dry_run.py; S1 discrimination B1-sufficient vs B2a/B3/compiler-insufficient restored |
| 5 | R2: records published into repo `docs/records/` (Records 6–8 + pre-flight summary + README) | commit `410026e` |
| 6 | R5: future RC tag package staged (name, message draft, pre-tag mechanical checklist; staging-only blanks) | `RC_TAG_PACKAGE.md` |
| 7 | R3: full verification re-run after all changes | **18/18 tests pass**; canonical dry-run A1/A2 PASS |

## Soak findings (honest)

- 708/1,180 runs score 1.0; **472 imperfect runs are confined to exactly 2 scenario families**
  (`…_and_location`, `find_days_till_holiday`) whose gold trajectories require RapidAPI
  network tools (`search_location_around_lat_lon`, `search_holiday`) — uncallable in this
  sandbox (no RAPID_API_KEY, network-blocked). **Not a harness defect**; on the real pilot the
  models call these tools with network access. Mock scores are policy-determinism checks, not pilot results.
- Zero exceptions in the final log; zero records lost; append-only discipline held.

## Remaining — need your help (nothing else blocks)

| # | Item | Your step |
|---|---|---|
| H1 | H100 machine | Rent per spec (SXM5 80GB, ≥16 vCPU, ≥128GB RAM, ≥500GB NVMe, Docker+network) |
| H2 | Staging execution (approved M1) | On the machine: run `staging_smoke_runsheet.md` §0–§3 — digest pull/match, weight download+hash verify, per-model launch smoke + peak memory, gemma probe, measured calibration |
| H3 | Day-2 audit slot (~2h) | Tell me the slot → I set the reminder |
| H4 | Main-run approval | After staging evidence (B5 package) → forward advisor's go |
| H5 | Credential close-out | Revoke GitHub PAT after the final RC tag push |
