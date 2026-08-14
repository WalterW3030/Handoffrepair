"""ITEM 2 — Enumerated run manifest generator (deterministic).

Enumerates every (pair, column, switch_point, episode, seed) run. Cell
counts are SIZED FROM MEASUREMENT, not asserted: the Day-1 calibration
measures per-cell GPU-seconds/tokens; the manifest is then regenerated with
measured values. The generator is frozen; its inputs (episode set,
episodes-per-cell, seed count) come from configs.

Sizing model (per pair):
  cells = 5 columns x 3 switch points = 15
  runs  = cells x episodes_per_cell(E) x seeds(S)
GPU-h  = runs x measured_seconds_per_run(pair) / 3600  +  3 model-load events
"""
import itertools, json


def enumerate_runs(pairs, columns, switch_points, episodes, seeds,
                   measured_sec_per_run=None, tokens_per_run=None):
    runs = []
    for pair, col, sp, ep, seed in itertools.product(
            pairs, columns, switch_points, episodes, seeds):
        r = {"pair": pair, "column": col, "switch_point": sp,
             "episode_id": ep, "seed": seed,
             "est_gpu_seconds": (measured_sec_per_run or {}).get(pair),
             "est_tokens": (tokens_per_run or {}).get(pair)}
        runs.append(r)
    return runs


def summarize(runs):
    by_pair = {}
    for r in runs:
        b = by_pair.setdefault(r["pair"], {"runs": 0, "gpu_seconds": 0.0, "tokens": 0})
        b["runs"] += 1
        b["gpu_seconds"] += r["est_gpu_seconds"] or 0
        b["tokens"] += r["est_tokens"] or 0
    total_h = sum(b["gpu_seconds"] for b in by_pair.values()) / 3600
    return {"total_runs": len(runs), "by_pair": by_pair,
            "total_gpu_hours": round(total_h, 2)}
