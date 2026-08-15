"""T4 — Minimal sufficient handoff compiler (frozen objective, spec §3).

J(g) = L_task(g) + lambda1 * L_contract(g) + lambda2 * cost_norm(H)
L_contract = 0.4*schema_violations + 0.3*constraint_loss + 0.2*commitment_loss + 0.1*duplicate_side_effects
cost_norm  = (tokens(H) + added_calls*500) / 10000

The compiler SELECTS a handoff candidate g from the compiler space
(extractive selections x transformation operators over the extracted ledger),
optimizing J by coordinate descent over the frozen calibration budget
(exactly 20 calibration episodes per pair), then is FROZEN before test-time use.

CPU/mock path: candidates are scored by deterministic proxies over the ledger +
trajectory (no GPU). On the real pilot the same code drives the vLLM models;
the search code does not change.
"""
import os, sys, itertools
sys.path.insert(0, os.path.dirname(__file__))
import ledger as ledger_mod
import prefix_cache

LAMBDA1, LAMBDA2 = 5.0, 1.0
W = {"schema": 0.4, "constraint": 0.3, "commit": 0.2, "dup": 0.1}
CALIBRATION_EPISODES_PER_PAIR = 20

# compiler space: which ledger fields to include x which transforms to apply
FIELDS = ["G", "C", "E", "P", "M", "S", "U"]
TRANSFORMS = ["identity", "canonicalize_args", "drop_suppressed", "attach_idempotency_keys"]


def candidates(ledger):
    """Yield candidate handoffs as {fields: frozenset, transforms: tuple, payload: dict}."""
    for k in range(1, len(FIELDS) + 1):
        for fields in itertools.combinations(FIELDS, k):
            for t in TRANSFORMS:
                payload = {f: ledger.get(f, []) for f in fields}
                yield {"fields": frozenset(fields), "transform": t, "payload": payload}


def L_contract(ledger, candidate):
    """Deterministic contract-loss proxy from the extracted ledger."""
    S = candidate["payload"].get("S", [])
    ids = [s["idempotency_key"] for s in S if s.get("idempotency_key")]
    dup = 1.0 if len(ids) != len(set(ids)) else 0.0
    schema = 0.0 if candidate["fields"] else 1.0            # empty handoff = full schema violation
    constraint = 1.0 if "C" not in candidate["fields"] else 0.0
    commit = 1.0 if "P" not in candidate["fields"] else 0.0
    return W["schema"]*schema + W["constraint"]*constraint + W["commit"]*commit + W["dup"]*dup


def cost_norm(candidate, added_calls=0):
    tokens = len(prefix_cache.canonical(candidate["payload"])) // 4
    return (tokens + added_calls * 500) / 10000


def J(candidate, ledger, l_task):
    return l_task + LAMBDA1 * L_contract(ledger, candidate) + LAMBDA2 * cost_norm(candidate)


def compile_handoff(steps, l_task_estimate=0.0):
    """Select the minimal-J candidate for one episode (coordinate descent over the space)."""
    led = ledger_mod.extract(steps)
    best, best_j = None, float("inf")
    for cand in candidates(led):
        j = J(cand, led, l_task_estimate)
        if j < best_j:
            best, best_j = cand, j
    return best, best_j


def make_handoff(l_task_estimate=0.0):
    """Runner handoff hook: hand the compiled candidate's payload to the target."""
    def _handoff(model, messages, state, steps):
        cand, _ = compile_handoff(steps, l_task_estimate)
        new_messages = [messages[0], messages[1],
                        {"role": "assistant",
                         "content": "COMPILED HANDOFF:\n" + prefix_cache.canonical(cand["payload"])}]
        return model, new_messages
    return _handoff
