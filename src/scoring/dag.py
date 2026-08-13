"""A5 — Milestone/minefield DAG scorer. Deterministic; no LLM judge (advisor requirement).

Mirrors ToolSandbox semantics:
  - milestones: world-state predicates that must be reached (weighted)
  - edges kind="similar": achieving src gives partial credit (credit fraction) for dst
  - minefields: predicates that must never be reached; any hit => episode failure
  - success = no minefield hit AND full milestone weight (incl. partial credit) achieved

Predicates use dotted keys over a state dict:
  "alarm"               scalar equality
  "messages.any.to"     any element of a list matches
  "events.any.title"    any element of a list matches
"""


def _resolve(state, key):
    parts = key.split(".")
    cur = state
    for i, p in enumerate(parts):
        if p == "any":
            rest = ".".join(parts[i + 1:])
            return [_resolve(el, rest) for el in cur] if rest else list(cur)
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _matches(pred, state):
    for key, want in pred.items():
        got = _resolve(state, key)
        if isinstance(got, list):
            if want not in got:
                return False
        elif got != want:
            return False
    return True


def score(trajectory, dag):
    """trajectory: list of world-state snapshots (one per executed step)."""
    milestones = dag.get("milestones", [])
    edges = dag.get("edges", [])
    minefields = dag.get("minefields", [])

    achieved = {m["id"] for m in milestones
                if any(_matches(m["predicate"], st) for st in trajectory)}

    partial = {}
    for e in edges:
        if e.get("kind") == "similar" and e["src"] in achieved and e["dst"] not in achieved:
            m = next((m for m in milestones if m["id"] == e["dst"]), None)
            if m:
                partial[e["dst"]] = round(m["weight"] * e.get("credit", 0.5), 6)

    mine_hits = [f["id"] for f in minefields
                 if any(_matches(f["predicate"], st) for st in trajectory)]

    total = sum(m["weight"] for m in milestones)
    gained = sum(m["weight"] for m in milestones if m["id"] in achieved) + sum(partial.values())
    raw = round(gained / total, 6) if total else 0.0

    return {
        "success": (not mine_hits) and abs(gained - total) < 1e-9,
        "raw": raw,
        "milestones_hit": sorted(achieved),
        "partial_credit": partial,
        "minefields_hit": mine_hits,
    }
