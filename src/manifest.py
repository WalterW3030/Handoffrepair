"""ITEM 2/3 — Enumerated run manifest generator (deterministic).

SINGLE SOURCE OF TRUTH: configs/sizing.yaml. The manifest is generated ONLY
from it. B0 has no switch point and is enumerated per (pair, episode, seed)
only — never crossed with switch points. Planning rates and measured rates
are kept in separate fields; totals are computed from whichever is present,
and labelled.
"""
import itertools, os, sys, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_sizing():
    with open(os.path.join(ROOT, "configs", "sizing.yaml")) as f:
        return yaml.safe_load(f)


def enumerate_runs(sizing, episodes, measured=None):
    """Return list of run dicts. `measured` = {pair: {"sec": float, "tokens": int}} or None."""
    s = sizing["pilot"]
    rates = sizing["rates"]
    plan = rates["planning_seconds_per_run"]
    runs = []

    def rate(pair):
        if measured and pair in measured:
            return {"sec": measured[pair]["sec"], "tokens": measured[pair]["tokens"], "rate_kind": "measured"}
        return {"sec": plan[pair], "tokens": None, "rate_kind": "planning"}

    for pair in s["pairs"]["calibrated"]:
        for col in s["columns_calibrated"]:
            sps = [None] if col == "B0" else s["switch_points"]   # B0: no switch point
            for sp, ep, seed in itertools.product(sps, episodes, s["seeds_calibrated"]):
                r = {"pair": pair, "column": col, "switch_point": sp,
                     "episode_id": ep, "seed": seed, **rate(pair)}
                runs.append(r)
    for pair in s["pairs"]["heldout"]:
        for col in s["columns_heldout"]:
            sps = [None] if col == "B0" else s["switch_points"]
            for sp, ep, seed in itertools.product(sps, episodes, s["seeds_heldout"]):
                r = {"pair": pair, "column": col, "switch_point": sp,
                     "episode_id": ep, "seed": seed, **rate(pair)}
                runs.append(r)
    return runs


def summarize(runs, sizing):
    by_pair = {}
    kind = "measured" if all(r["rate_kind"] == "measured" for r in runs) else "planning"
    for r in runs:
        b = by_pair.setdefault(r["pair"], {"runs": 0, "gpu_seconds": 0.0, "tokens": 0})
        b["runs"] += 1
        b["gpu_seconds"] += r["sec"] or 0
        b["tokens"] += r["tokens"] or 0
    compute_h = sum(b["gpu_seconds"] for b in by_pair.values()) / 3600
    b = sizing["budget"]
    total_h = compute_h + b["model_load_overhead_h"] + b["b6_yardstick_h"]
    return {"total_runs": len(runs), "rate_kind": kind, "by_pair": by_pair,
            "compute_gpu_hours": round(compute_h, 2),
            "overheads": {"model_load_h": b["model_load_overhead_h"],
                          "b6_yardstick_h": b["b6_yardstick_h"], "b6_rollouts": b["b6_rollouts"]},
            "total_gpu_hours": round(total_h, 2),
            "within_cap": total_h <= b["hard_gpu_hour_cap"]}
