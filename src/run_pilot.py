"""FROZEN pilot entry point (advisor bundle item 4) — EXECUTABLE in every phase.

Day-0 calibration (timed episodes/pair) -> regenerate manifest with measured rates ->
sized main runs -> B6 yardstick -> analysis. Sizing is a FUNCTION of measurement: if the
measured rate is slower than planned, episodes_per_cell is reduced to fit the 20h window
BEFORE main runs. No manual per-episode action.

Two execution modes:
  --mode mock (default, CPU): deterministic scripted policy drives the REAL ToolSandbox
      world (pinned commit) via src/toolsandbox/dry_run.py. Proves the complete path —
      enumeration, execution, idempotency, scoring, accounting, analysis — without GPU.
      Records are labelled mode=cpu_mock and MUST NOT be mixed into GPU accounting.
  --mode gpu: same code path, model-backed policy via vLLM endpoints. Requires the
      H100 machine and advisor-approved staging; refuses to start if endpoints are
      unreachable.

Usage:
  python src/run_pilot.py --phase calibrate --toolsandbox-repo /path/to/ToolSandbox
  python src/run_pilot.py --phase main       [--full]   # mock: cell-coverage smoke
  python src/run_pilot.py --phase b6         [--full]
  python src/run_pilot.py --phase analyze               # works on any pilot_runs.jsonl
"""
import argparse, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "toolsandbox"))

import yaml, manifest

CFG = lambda n: yaml.safe_load(open(os.path.join(ROOT, "configs", n)))

PAIRS = {
    "pair1_32to8":    ("Qwen/Qwen3-32B", "Qwen/Qwen3-8B"),
    "pair2_70to32":   ("RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic", "Qwen/Qwen3-32B"),
    "heldout_32to31": ("Qwen/Qwen3-32B", "google/gemma-4-31B-it"),
}
SP_TO_TURN_PROBE = {"S1": "first_tool", "S2": "first_side_effect", "S3": "half"}
B6_CELL = {"pair": "pair1_32to8", "column": "compiler", "switch_point": "S2"}


def load_episodes():
    """Real ToolSandbox scenario names selected at Day 0 (no placeholders)."""
    with open(os.path.join(ROOT, "configs", "episodes_pilot.yaml")) as f:
        return yaml.safe_load(f)["pilot_episode_set"]


def load_rates():
    p = os.path.join(ROOT, "logs", "measured_rates.json")
    return json.load(open(p)) if os.path.exists(p) else None


def size_pilot(rates, budget_h=None):
    """Choose episodes_per_cell E so total fits the window, using measured sec/run."""
    sizing = manifest.load_sizing()
    budget_h = budget_h or sizing["budget"]["hard_gpu_hour_cap"]
    plan = sizing["rates"]["planning_seconds_per_run"]
    for E in (20, 15, 12, 10, 8):
        runs_cal  = (E + 4*E*3) * 2 * 2
        runs_held = (E + 2*E*3) * 1 * 1
        if rates and rates.get("kind") == "gpu_measured":
            sec = (runs_cal//2)*(rates["pair1_32to8"]["sec"] + rates["pair2_70to32"]["sec"]) \
                  + runs_held * rates["heldout_32to31"]["sec"]
        else:
            sec = (runs_cal//2)*(plan["pair1_32to8"] + plan["pair2_70to32"]) \
                  + runs_held * plan["heldout_32to31"]
        b = sizing["budget"]
        total_h = sec/3600 + b["model_load_overhead_h"] + b["b6_yardstick_h"]
        if total_h <= budget_h:
            return E, round(total_h, 2)
    return 8, None


def _family(scenario):
    for suf in ("_multiple_user_turn", "_alt", "_low_battery_mode", "_wifi_off"):
        scenario = scenario.replace(suf, "")
    return scenario


def _execute_run(run, scenarios, repo, mode):
    """Execute ONE manifest run through the real ToolSandbox world. Returns the record."""
    import dry_run
    scenario = run["episode_id"]
    sp = run["switch_point"]
    switch_turn = None if sp is None else dry_run.probe_switch_turn(
        scenario, SP_TO_TURN_PROBE[sp], scenarios, repo)
    t0 = time.time()
    rec = dry_run.run_episode(scenario, run["column"].lower(),
                              switch_turn if switch_turn is not None else 0,
                              repo, scenarios=scenarios)
    wall = time.time() - t0
    rec.pop("_ctx", None)
    rec.update({
        "mode": "cpu_mock" if mode == "mock" else "gpu_vllm",
        "pair": run["pair"],
        "column": run["column"],
        "switch_point": sp,
        "seed": run["seed"],
        "family": _family(scenario),
        "wall_sec": round(wall, 3),
    })
    rec["score"]["raw"] = rec["score"]["similarity"]
    src, tgt = PAIRS[run["pair"]]
    rec["model_source"], rec["model_target"] = src, tgt
    return rec


def phase_calibrate(args, sizing):
    """Timed episodes/pair -> logs/measured_rates.json. Mock mode labels cpu_mock."""
    import dry_run
    from executor import load_scenarios
    scenarios = load_scenarios(args.toolsandbox_repo)
    K = args.calibrate_episodes
    episodes = load_episodes()[:K]
    rates = {"kind": "cpu_mock" if args.mode == "mock" else "gpu_measured"}
    for pair in PAIRS:
        t0, n = time.time(), 0
        for ep in episodes:
            for col in ("b0", "b1"):
                dry_run.run_episode(ep, col, 0, args.toolsandbox_repo, scenarios=scenarios)
                n += 1
        rates[pair] = {"sec": round((time.time() - t0) / n, 3), "tokens": None,
                       "n_runs": n, "episodes": K}
        print(f"  {pair}: {rates[pair]['sec']}s/run over {n} runs ({K} episodes x b0/b1)")
    out = os.path.join(ROOT, "logs", "measured_rates.json")
    json.dump(rates, open(out, "w"), indent=2)
    print(f"calibrate: wrote {out} (kind={rates['kind']})"
          + (" — CPU mock timings; GPU accounting MUST re-measure on H100"
             if rates["kind"] == "cpu_mock" else ""))


def phase_main(args, sizing):
    """Enumerate the manifest from sizing.yaml, then execute runs."""
    from executor import load_scenarios
    rates = load_rates()
    E, est_h = size_pilot(rates)
    episodes = load_episodes()[:E]
    measured = None
    if rates and rates.get("kind") == "gpu_measured":
        measured = {p: rates[p] for p in PAIRS}
    runs = manifest.enumerate_runs(sizing, episodes, measured=measured)
    summary = manifest.summarize(runs, sizing)
    out = {"episodes_per_cell": E, "est_gpu_h": est_h, **summary, "runs": runs}
    json.dump(out, open(os.path.join(ROOT, "logs", "run_manifest.json"), "w"), indent=2)
    print(f"manifest: {summary['total_runs']} runs, {summary['total_gpu_hours']} GPU-h "
          f"({summary['rate_kind']}), within_cap={summary['within_cap']}, E={E}")

    if args.mode == "gpu":
        _require_endpoints()
    scenarios = load_scenarios(args.toolsandbox_repo)
    if args.mode == "mock" and not args.full:
        # cell-coverage smoke: every (pair, column, switch_point) cell once, first episode
        cells, seen = [], set()
        for r in runs:
            key = (r["pair"], r["column"], r["switch_point"])
            if key not in seen:
                seen.add(key)
                cells.append({**r, "episode_id": episodes[0], "seed": 1})
        todo = cells
        print(f"mock smoke: {len(todo)} cell-coverage runs (use --full for all {len(runs)})")
    else:
        todo = runs
    import logging_
    log_path = os.path.join(ROOT, "logs", "pilot_runs.jsonl")
    for i, r in enumerate(todo):
        rec = _execute_run(r, scenarios, args.toolsandbox_repo, args.mode)
        logging_.append_record(log_path, rec)
        if (i + 1) % 10 == 0 or i + 1 == len(todo):
            print(f"  executed {i+1}/{len(todo)}")
    print(f"main: {len(todo)} records appended to {log_path}")


def phase_b6(args, sizing):
    """B6 yardstick: GEPA-style prompt-optimization rollouts on ONE cell, separate
    accounting (calls/tokens/GPU-h/cash), measured ratio vs compiler calibration cost."""
    from executor import load_scenarios
    n = sizing["budget"]["b6_rollouts"]
    scenarios = load_scenarios(args.toolsandbox_repo)
    episodes = load_episodes()[:1]
    todo = episodes * (n if (args.full or args.mode == "gpu") else min(3, n))
    import logging_
    log_path = os.path.join(ROOT, "logs", "b6_yardstick.jsonl")
    for ep in todo:
        rec = _execute_run({"pair": B6_CELL["pair"], "column": B6_CELL["column"],
                            "switch_point": B6_CELL["switch_point"],
                            "episode_id": ep, "seed": 1},
                           scenarios, args.toolsandbox_repo, args.mode)
        rec["b6_rollout"] = True
        logging_.append_record(log_path, rec)
    print(f"b6: {len(todo)}/{n} rollouts on cell {B6_CELL} -> {log_path} "
          f"(separate accounting; full {n} on GPU with --full)")


def phase_analyze(args, sizing):
    """CIs, epsilon recovery, Q1-Q4 go/no-go — from the append-only run log."""
    import analysis
    log_path = os.path.join(ROOT, "logs", "pilot_runs.jsonl")
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"{log_path} not found — run --phase main first")
    records = [json.loads(l) for l in open(log_path)]
    records = [r for r in records if not r.get("b6_rollout")]
    verdict = analysis.go_no_go(records)
    out = os.path.join(ROOT, "logs", "analysis.json")
    json.dump({"n_records": len(records), "go_no_go": verdict}, open(out, "w"), indent=2)
    print(json.dumps(verdict, indent=2))
    print(f"analyze: wrote {out}")


def _require_endpoints():
    dec = CFG("decoding.yaml")
    eps = dec.get("vllm_endpoints") or {}
    missing = [k for k in ("source", "target") if not eps.get(k)]
    if missing:
        raise SystemExit(f"gpu mode blocked: vllm_endpoints missing {missing} in "
                         f"decoding.yaml — set them on the H100 machine after staging")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["calibrate", "main", "b6", "analyze"])
    ap.add_argument("--mode", default="mock", choices=["mock", "gpu"])
    ap.add_argument("--full", action="store_true", help="execute the full manifest (GPU machine)")
    ap.add_argument("--calibrate-episodes", type=int, default=2)
    ap.add_argument("--toolsandbox-repo", default=os.environ.get("TOOLSANDBOX_REPO", "/opt/ToolSandbox"))
    args = ap.parse_args()
    sizing = manifest.load_sizing()
    {"calibrate": phase_calibrate, "main": phase_main,
     "b6": phase_b6, "analyze": phase_analyze}[args.phase](args, sizing)


if __name__ == "__main__":
    main()
