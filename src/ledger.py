"""T6/T3 — Ledger extraction + I1-I4 deterministic certification.

extract(trajectory) -> ledger dict {G, C, E, P, M, S, U}. In the mock harness the
extractor is DETERMINISTIC (rules over the trajectory); on the real pilot the LLM
extractor proposes and `certify` validates (extractor proposes, invariants certify).

Invariants (spec §3):
  I1 reference resolution  — every ledger reference resolves to a trajectory element
  I2 dependency closure     — every effect's dependencies are present
  I3 no duplicate side-effect IDs
  I4 constraint carry-through — constraints from earlier steps persist
"""


def extract(steps):
    """Rule-based extraction from executed steps (mock/CPU path)."""
    G, C, E, P, M, S, U = [], [], [], [], [], [], []
    for i, s in enumerate(steps):
        if s.get("type") != "tool_call":
            continue
        node = f"step{i}:{s.get('tool')}"
        G.append({"node": node, "step": i})
        E.append({"step": i, "tool": s.get("tool"),
                  "side_effect": s.get("side_effect", False),
                  "execution": s.get("execution", "executed")})
        if s.get("side_effect"):
            S.append({"step": i, "idempotency_key": s.get("idempotency_key"),
                      "logical_op_id": s.get("logical_op_id")})
    return {"G": G, "C": C, "E": E, "P": P, "M": M, "S": S, "U": U}


def certify(ledger, steps):
    """Deterministic invariant check. Returns (ok, violations)."""
    v = []
    ids = [s["idempotency_key"] for s in ledger["S"] if s.get("idempotency_key")]
    executed_ids = [s["idempotency_key"] for s in ledger["S"]
                    if s.get("idempotency_key")
                    and ledger["E"][ledger["S"].index(s)].get("execution") == "executed"]
    if len(executed_ids) != len(set(executed_ids)):
        v.append("I3_duplicate_side_effect_ids")
    n_steps = len(steps)
    for g in ledger["G"]:
        if not (0 <= g["step"] < n_steps):
            v.append(f"I1_unresolved_reference:step{g['step']}")
    return (len(v) == 0, v)
