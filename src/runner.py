"""A3/A4 — Episode runner: executes one episode for one column.

Columns implemented here (A4):
  b0 — target-from-start: fresh episode, target model runs everything (no switch)
  b1 — raw switch: source runs until the switch point, prefix snapshot is
       logged, target continues from the IDENTICAL prefix + world state

Later columns (b2a matched-token summary, b3 fixed typed state, compiler)
plug into the same run() via the `handoff` hook — Day 2/3 work, not Part A.

Strict pairing guarantee: b1 logs prefix_ids["switch"]; the smoke suite
re-runs each (episode, switch_point) twice and asserts identical IDs.
"""
import copy, datetime, os, sys, uuid

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scoring"))

import world, prefix_cache, switch_points, logging_
from scoring import dag as dag_scorer

# uuid5 namespace for stable logical-operation IDs (item 6)
_OP_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class TransportError(Exception):
    """Transport-level failure (5xx/connection) — retryable, reuses the logical op-ID.
    A parsed-but-wrong action is DATA (semantic_retries=0), never a TransportError."""


class IdempotencyLedger:
    """Issues/carries logical operation IDs and enforces duplicate suppression.

    Operation identity is CONTENT-BASED (episode, tool, canonical args) — NOT positional —
    so a target that repeats an already-completed state-changing call after handoff maps to
    the SAME logical operation and is suppressed. A single logical operation may have several
    attempts (transport retries); all share the logical_op_id, each gets its own attempt_no.
    """

    def __init__(self, episode_id):
        self.episode_id = episode_id
        self.ops = {}        # logical_op_id -> {"status": ..., "result": ..., "key": ...}

    def _op_id(self, tool, canonical_args):
        return str(uuid.uuid5(_OP_NS, prefix_cache.canonical(
            {"episode_id": self.episode_id, "tool": tool, "canonical_args": canonical_args})))

    def key(self, tool, canonical_args):
        return prefix_cache.hashlib.sha256(prefix_cache.canonical(
            {"tool": tool, "canonical_args": canonical_args,
             "logical_op_id": self._op_id(tool, canonical_args)}).encode()).hexdigest()

    def before_execute(self, tool, canonical_args, side_effect):
        """Pre-execution lookup. Returns (logical_op_id, idem_key, decision, prior_result).
        decision in: 'execute' | 'suppress' (duplicate side-effect already done)."""
        oid = self._op_id(tool, canonical_args)
        key = self.key(tool, canonical_args)
        prior = self.ops.get(oid)
        if side_effect and prior and prior["status"] == "executed":
            return oid, key, "suppress", prior["result"]
        return oid, key, "execute", None

    def record(self, oid, key, status, result=None):
        """status in: 'executed' | 'suppressed' | 'replayed'. A 'suppressed' attempt must NOT
        overwrite a prior 'executed' record — the operation stays executed for future lookups."""
        prior = self.ops.get(oid)
        if status == "suppressed" and prior and prior["status"] == "executed":
            return                       # keep the executed record (and its result)
        self.ops[oid] = {"status": status, "result": result, "key": key}


def _derive(state):
    """Derived flags consumed by DAG predicates (see synthetic_episodes)."""
    s = dict(state)
    events = s.get("events", [])
    s["old_meeting_present"] = any(e["title"] == "old_meeting" for e in events)
    days = [e["day"] for e in events]
    s["double_booking"] = len(days) != len(set(days))
    return s


def run(episode, column, switch_point, source, target, seed, log_path,
        world_impl=None, handoff=None, retry_config=None):
    world_impl = world_impl or world.TOOLS
    messages = [{"role": "system", "content": episode["system"]},
                {"role": "user", "content": episode["user"]}]
    state = copy.deepcopy(episode["initial_state"])
    trajectory = [_derive(copy.deepcopy(state))]
    steps, prefix_ids, checks_fired = [], {}, []
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    ledger = IdempotencyLedger(episode["episode_id"])   # carried across the handoff:
    # the target inherits the source's executed operations, so cross-handoff duplicates suppress

    # b0: target runs from the start (no handoff). All handoff columns (b1/b2a/b3/compiler)
    # run the SOURCE to the switch point first — this produces the shared prefix snapshot that
    # strict pairing compares across columns.
    model = target if column == "b0" else source
    expected_len = len(episode["source_script"])
    switched = False
    retry_cfg = (retry_config or {}).get("retry_rule", {})
    max_transport_retries = retry_cfg.get("max_transport_retries", 3)

    for _ in range(episode["max_turns"]):
        # --- transport-level retry: same logical operation, reused op-ID (advisor item 5) ---
        attempt, out = 0, None
        while True:
            try:
                out = model.generate(messages, tools=list(world_impl))
                break
            except TransportError as te:
                attempt += 1
                if attempt > max_transport_retries:
                    raise
                checks_fired.append(f"transport_retry:{attempt}")
                continue                        # retry SAME turn; op-ID assigned below is stable
        act = out["action"]
        usage["prompt_tokens"] += out["usage"]["prompt_tokens"]
        usage["completion_tokens"] += out["usage"]["completion_tokens"]

        step = {"model": model.name, **act}
        if act["type"] == "tool_call":
            spec = world_impl[act["tool"]]
            canonical_args = act.get("args", {})
            step["side_effect"] = spec["side_effect"]
            # 1. ISSUE/CARRY the logical-op ID and key BEFORE execution (advisor item 5)
            oid, key, decision, prior = ledger.before_execute(
                act["tool"], canonical_args, spec["side_effect"])
            step["logical_op_id"] = oid
            step["idempotency_key"] = key
            # 2. PRE-EXECUTION suppression: duplicate side-effect => do NOT re-execute
            if decision == "suppress":
                step["execution"] = "suppressed"          # logged: not performed
                step["result"] = prior                    # reuse prior result, world unchanged
                checks_fired.append("V3_duplicate_suppressed")
            else:
                step["result"] = spec["fn"](state, canonical_args)   # execute once
                step["execution"] = "executed"
            ledger.record(oid, key, step["execution"], step["result"])
            messages.append({"role": "assistant", "content": prefix_cache.canonical(act)})
            messages.append({"role": "tool", "content": prefix_cache.canonical(step["result"])})
        else:
            step["side_effect"] = False
            messages.append({"role": "assistant", "content": act["content"]})

        steps.append(step)
        trajectory.append(_derive(copy.deepcopy(state)))

        # --- handoff logic (all handoff columns share the identical prefix snapshot) ---
        if column != "b0" and switch_point is not None and not switched and \
                switch_points.reached(steps, switch_point, expected_len):
            prefix_ids["switch"] = prefix_cache.prefix_id(messages)
            checks_fired.append(f"switch_reached:{switch_point}")
            # every column receives the SAME messages + world snapshot; the hook decides
            # what the target actually continues from (raw transcript / summary / typed state
            # / compiled handoff). prefix_ids["switch"] is the pairing anchor for all columns.
            if handoff:
                model, messages = handoff(model=target, messages=messages, state=state,
                                          steps=steps)
            else:
                model = target
            switched = True

        if act["type"] == "message":
            break

    score = dag_scorer.score(trajectory, episode["dag"])
    record = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "episode_id": episode["episode_id"],
        "column": column,
        "switch_point": switch_point,
        "seed": seed,
        "model_source": source.name,
        "model_target": target.name,
        "prefix_ids": prefix_ids,
        "steps": steps,
        "checks_fired": checks_fired,
        "gate_branch": None,                # gate arrives Day 2
        "usage": usage,
        "gpu_h": 0.0, "cash": 0.0,          # CPU mock; real values on GPU
        "score": score,
    }
    if log_path:
        logging_.append_record(log_path, record)
    return record
