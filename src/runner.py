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
import copy, datetime, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scoring"))

import world, prefix_cache, switch_points, logging_
from scoring import dag as dag_scorer


def _derive(state):
    """Derived flags consumed by DAG predicates (see synthetic_episodes)."""
    s = dict(state)
    events = s.get("events", [])
    s["old_meeting_present"] = any(e["title"] == "old_meeting" for e in events)
    days = [e["day"] for e in events]
    s["double_booking"] = len(days) != len(set(days))
    return s


def run(episode, column, switch_point, source, target, seed, log_path,
        world_impl=None, handoff=None):
    world_impl = world_impl or world.TOOLS
    messages = [{"role": "system", "content": episode["system"]},
                {"role": "user", "content": episode["user"]}]
    state = copy.deepcopy(episode["initial_state"])
    trajectory = [_derive(copy.deepcopy(state))]
    steps, prefix_ids, checks_fired = [], {}, []
    usage = {"prompt_tokens": 0, "completion_tokens": 0}

    model = source if column == "b1" else target
    expected_len = len(episode["source_script"])
    switched = False

    for _ in range(episode["max_turns"]):
        out = model.generate(messages, tools=list(world_impl))
        act = out["action"]
        usage["prompt_tokens"] += out["usage"]["prompt_tokens"]
        usage["completion_tokens"] += out["usage"]["completion_tokens"]

        step = {"model": model.name, **act}
        if act["type"] == "tool_call":
            spec = world_impl[act["tool"]]
            step["side_effect"] = spec["side_effect"]
            step["result"] = spec["fn"](state, act.get("args", {}))
            step["idempotency_key"] = prefix_cache.hashlib.sha256(
                prefix_cache.canonical(
                    {"tool": act["tool"], "canonical_args": act.get("args", {}),
                     "episode_id": episode["episode_id"]}).encode()).hexdigest()
            messages.append({"role": "assistant", "content": prefix_cache.canonical(act)})
            messages.append({"role": "tool", "content": prefix_cache.canonical(step["result"])})
        else:
            step["side_effect"] = False
            messages.append({"role": "assistant", "content": act["content"]})

        steps.append(step)
        trajectory.append(_derive(copy.deepcopy(state)))

        # --- handoff logic ---
        if column == "b1" and not switched and \
                switch_points.reached(steps, switch_point, expected_len):
            prefix_ids["switch"] = prefix_cache.prefix_id(messages)
            checks_fired.append(f"switch_reached:{switch_point}")
            model = handoff(model=target, messages=messages, state=state) if handoff else target
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
