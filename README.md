# HandoffRepair Pilot — Frozen Pipeline Repo

Pilot pipeline for RD-2 HandoffRepair, built per `HandoffRepair Pilot — Tasks, Goals & One-Week Plan.md`
and Advisor Instructions 3 (2026-08-08). Tag `pilot-freeze-v1` is applied at Day 0; after the tag,
**no per-episode manual correction** — the only manual touch is the predeclared 10% extraction audit (Day 2).

## Layout

| Path | Contents | Part-A task |
|---|---|---|
| `configs/` | Frozen spec §3, seed table, model pins, episode set, switch-point defs | A1 |
| `src/mock_model.py` | Deterministic stub model for CPU validation | A2 |
| `src/world.py` | Mini stateful-tool world simulator (ToolSandbox interface mirror) | A5 support |
| `src/scoring/dag.py` | Milestone/minefield DAG scorer (deterministic, no LLM judge) | A5 |
| `src/scoring/synthetic_episodes.py` | Synthetic scenarios with hand-computed expected scores | A5 |
| `src/switch_points.py` | Semantic switch-point detection S1–S3 | A7 |
| `src/runner.py`, `src/prefix_cache.py` | Episode runner + strict-pairing prefix layer | A3 |
| `src/columns/` | B0 (target-from-start), B1 (raw switch) | A4 |
| `src/toolsandbox/` | Integration doc + self-contained scenario selector | A6 |
| `serving/` | vLLM serve scripts per model + Gemma tool-call shim | A8 |
| `smoke/run_smoke.py` | End-to-end CPU dry run: 5 eps × B0/B1 × S1–S3 | A9 |
| `tests/test_scorer.py` | Scorer verification vs hand-computed values | A5 |
| `logs/` | Append-only run log (JSONL), written at runtime | A1 schema |

## Freeze protocol

1. Day 0: prerequisites P1–P6 verified (weights hashed, vLLM pinned, scenarios restricted) → tag `pilot-freeze-v1`.
2. Post-tag: any bug fix requires new tag + changelog entry + rerun of affected cells from cached prefixes.
3. Run log is append-only; every episode records inputs, prefix IDs, model hashes, checks fired, gate branch, cost.
