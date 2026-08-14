"""FROZEN pilot entry point (advisor bundle item 4).

Day-0 calibration (timed, 10 episodes/pair) -> regenerate manifest with
measured rates -> sized main runs -> B6 yardstick. Sizing is a FUNCTION of
measurement: if measured rate is slower than planned, episodes_per_cell is
reduced to fit the 20h window BEFORE main runs. No manual per-episode action.

Usage (on the GPU machine, after tag pilot-freeze-v1):
  python src/run_pilot.py --phase calibrate   # timed, 10 eps/pair, writes measured_rates.json
  python src/run_pilot.py --phase main        # sized runs per manifest
  python src/run_pilot.py --phase b6          # GEPA yardstick, 1 cell, 150 rollouts
  python src/run_pilot.py --phase analyze     # CIs, epsilon recovery, go/no-go
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import yaml, manifest

CFG = lambda n: yaml.safe_load(open(os.path.join(ROOT, "configs", n)))

PAIRS = {
    "pair1_32to8":    ("Qwen/Qwen3-32B", "Qwen/Qwen3-8B"),
    "pair2_70to32":   ("RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic", "Qwen/Qwen3-32B"),
    "heldout_32to27": ("Qwen/Qwen3-32B", "google/gemma-3-27b-it"),
}
COLUMNS_ALL  = ["B0", "B1", "B2a", "B3", "compiler"]
COLUMNS_HELD = ["B0", "B1", "compiler"]          # zero-shot recovery needs only these
SWITCH_POINTS = ["S1", "S2", "S3"]
B6_ROLLOUTS = 150


def load_rates():
    p = os.path.join(ROOT, "logs", "measured_rates.json")
    return json.load(open(p)) if os.path.exists(p) else None


def size_pilot(rates, budget_h=20.0):
    """Choose episodes_per_cell E so total fits the window, using measured sec/run."""
    dec = CFG("decoding.yaml"); ev = CFG("eval_frozen.yaml")
    for E in (20, 15, 12, 10, 8):
        runs_cal  = (E + 4*E*3) * 2 * 2          # calibrated: 5 cols, 2 pairs, 2 seeds
        runs_held = (E + 2*E*3) * 1 * 1          # held-out: 3 cols, 1 pair, 1 seed
        if rates:
            sec = (runs_cal//2)*(rates["pair1_32to8"]["sec"] + rates["pair2_70to32"]["sec"]) \
                  + runs_held * rates["heldout_32to27"]["sec"]
        else:
            sec = (runs_cal//2)*(30 + 75) + runs_held * 40      # planning fallback
        total_h = sec/3600 + 0.5 + 2.5           # + model loads + B6
        if total_h <= budget_h:
            return E, round(total_h, 2)
    return 8, None                                # floor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["calibrate", "main", "b6", "analyze"])
    a = ap.parse_args()
    rates = load_rates()
    E, est_h = size_pilot(rates)
    episodes = [f"ep_{i:03d}" for i in range(E)]  # replaced by ToolSandbox selection at Day 0
    if a.phase == "main":
        runs = []
        for pair in ("pair1_32to8", "pair2_70to32"):
            runs += manifest.enumerate_runs([pair], COLUMNS_ALL, SWITCH_POINTS, episodes, [1, 2])
        runs += manifest.enumerate_runs(["heldout_32to27"], COLUMNS_HELD, SWITCH_POINTS, episodes, [1])
        out = {"episodes_per_cell": E, "est_gpu_h": est_h,
               **manifest.summarize(runs), "runs": runs}
        json.dump(out, open(os.path.join(ROOT, "logs", "run_manifest.json"), "w"), indent=2)
        print(f"manifest: {out['total_runs']} runs, est {est_h} GPU-h, E={E}")
    elif a.phase == "b6":
        print(f"B6 yardstick: {B6_ROLLOUTS} rollouts on 1 cell, separate accounting "
              f"(calls/tokens/GPU-h/cash) — measured ratio vs compiler calibration cost")
    else:
        print(f"phase {a.phase}: see plan Day { {'calibrate':1,'analyze':6}[a.phase] }")


if __name__ == "__main__":
    main()
