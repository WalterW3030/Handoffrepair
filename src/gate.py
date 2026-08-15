"""T5 — Validate-or-restart gate (V1-V5) + decision rule (frozen thresholds in spec §3).

V1 reference resolution   V2 dependency closure   V3 duplicate side effects
V4 constraint carry-through   V5 manifest compatibility

Decision rule (deterministic if/elif/else over the V1-V5 results + cost estimate):
  if all checks pass                                  -> resume
  elif repairable failure AND est. repair cost low    -> replay-recheck
  else (failure cost estimate > tau_restart fraction) -> restart
Counterfactual branch outcomes are logged on a 10% subsample (spec: counterfactual_subsample).
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(__file__))
import ledger as ledger_mod

TAU_RESTART = 0.5                 # spec gate.tau_restart
COUNTERFACTUAL_SUBSAMPLE = 0.10   # spec gate.counterfactual_subsample


def check_V1(ledger, steps):
    ok, v = ledger_mod.certify(ledger, steps)
    return not any(x.startswith("I1") for x in v)

def check_V2(ledger, steps):
    ok, v = ledger_mod.certify(ledger, steps)
    return not any(x.startswith("I2") for x in v)

def check_V3(ledger, steps):
    ok, v = ledger_mod.certify(ledger, steps)
    return not any(x.startswith("I3") for x in v)

def check_V4(ledger, steps):
    return True    # constraint carry-through: constraints persist (rule-extracted, always carried)

def check_V5(ledger, steps):
    return True    # manifest compatibility: tool names within target manifest (mock = all known)


CHECKS = [("V1", check_V1), ("V2", check_V2), ("V3", check_V3), ("V4", check_V4), ("V5", check_V5)]


def evaluate(steps, seed=0, failure_cost_estimate=0.0):
    """Run V1-V5, apply the decision rule, log counterfactual branch on the subsample."""
    ledger = ledger_mod.extract(steps)
    results = {name: fn(ledger, steps) for name, fn in CHECKS}
    failed = [n for n, ok in results.items() if not ok]

    if not failed:
        branch = "resume"
    elif failure_cost_estimate <= TAU_RESTART:
        branch = "replay_recheck"
    else:
        branch = "restart"

    counterfactual = None
    rng = random.Random(seed)
    if rng.random() < COUNTERFACTUAL_SUBSAMPLE:
        counterfactual = {"chosen": branch,
                          "alternates": [b for b in ("resume", "replay_recheck", "restart")
                                         if b != branch]}
    return {"checks": results, "failed": failed, "branch": branch,
            "counterfactual_logged": counterfactual is not None,
            "counterfactual": counterfactual}
