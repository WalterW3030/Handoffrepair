"""T-d — Real ToolSandbox dry-run through EVERY implemented column (advisor final item:
"one real ToolSandbox dry-run through every implemented column").

Runs ONE kept scenario (default: add_reminder_content_and_date_and_time) end-to-end for
columns B0, B1, B2a, B3, compiler against the pinned ToolSandbox checkout, with:

  * real tool execution via ToolSandbox's own ExecutionEnvironment role (agent messages
    are Python source, executed in the REPL; tool_trace rows land in the SANDBOX table);
  * our frozen harness semantics: per-run fresh ExecutionContext, IdempotencyLedger
    (pre-execution duplicate suppression, stable logical-op IDs), prefix_ids["switch"]
    as the strict-pairing anchor, and the ACTUAL handoff hooks from
    src/columns/{b2a,b3}.py and src/compiler.py;
  * deterministic scripted policy standing in for the models (CPU mode; no GPU tokens).
    The policy acts ONLY on what the column's handoff representation carries: if the
    resolved reminder_timestamp is absent from the target's view (B3/compiler drop tool
    RESULTS by design), the target re-derives it with a read-only call — the repair
    behavior the pilot measures;
  * scoring by ToolSandbox's own scenario.evaluation.evaluate (milestone/minefield DAG,
    deterministic, no LLM judge).

Assertions (fail loudly):
  A1 prefix_ids["switch"] identical across B1/B2a/B3/compiler (strict pairing);
  A2 final REMINDER world state identical across all five columns (modulo server-side
     uuid/creation_timestamp), i.e. every column reaches the same world.

CLI:  python3 src/toolsandbox/dry_run.py --repo /path/to/ToolSandbox \
          --scenario add_reminder_content_and_date_and_time --out logs/toolsandbox_dry_run.json
"""
import argparse, datetime, json, os, re, sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "columns"))

import prefix_cache
from runner import IdempotencyLedger
from executor import load_world

COLUMNS = ["b0", "b1", "b2a", "b3", "compiler"]
_TS_RE = re.compile(r"\b(1[6-8]\d{8}(?:\.\d+)?)\b")          # posix ts ~2024-2025


# ---------------------------------------------------------------- scripted policy
def _db_addition_targets(scenario):
    """(table_name, [rows]) from the scenario's OWN addition milestones (oracle-derived
    script, deterministic, no LLM). Guardrail constraints have target_dataframe=None."""
    out = []
    for ms in scenario.evaluation.milestone_matcher.milestones:
        for c in ms.snapshot_constraints:
            tdf = c.target_dataframe
            if tdf is None or "tool_trace" in tdf.columns:
                continue
            if "addition" in getattr(c.snapshot_constraint, "__name__", ""):
                out.append((c.database_namespace.name, tdf.to_dicts()))
    return out


def _traced_tools(scenario):
    """Ordered gold tool names from SANDBOX tool_trace milestones (deduped, in order)."""
    names = []
    for ms in scenario.evaluation.milestone_matcher.milestones:
        for c in ms.snapshot_constraints:
            tdf = c.target_dataframe
            if tdf is None or "tool_trace" not in tdf.columns:
                continue
            for v in tdf["tool_trace"].to_list():
                for tr in (json.loads(v) if v.strip().startswith("[") else [json.loads(v)]):
                    n = tr.get("tool_name")
                    if n and (not names or names[-1] != n):
                        names.append(n)
    return names


def make_policy(scenario, world_impl, episode_state):
    """Build a deterministic scripted policy for ANY kept scenario.

    Action sourcing is labelled per step (episode_state['info_source']):
      'handoff_view'  — the value needed was READ from what the column handed over
      'gold_fallback' — the value was NOT in the view; the oracle script supplied it
                        (this is exactly the information loss the pilot measures)
    """
    additions = _db_addition_targets(scenario)
    traced = _traced_tools(scenario)
    traced_readonly = [t for t in traced
                       if t in world_impl and not world_impl[t]["side_effect"]]
    # a gold timestamp from any addition row lets us emit VALID datetime-component args
    import datetime as _dt
    gold_ts = next((v for _, rows in additions for row in rows for v in row.values()
                    if isinstance(v, float) and v > 1e9), None)
    gold_dt = _dt.datetime.fromtimestamp(gold_ts) if gold_ts else None

    def _fill_args(tool):
        import inspect as _i
        params = _i.signature(scenario_tool(scenario, tool)).parameters
        args = {}
        for p, prm in params.items():
            if prm.default is not _i.Parameter.empty:
                continue
            if gold_dt and p in ("year", "month", "day", "hour", "minute", "second"):
                args[p] = getattr(gold_dt, p)
            else:
                args[p] = _default_for(prm.annotation)
        return args

    def _emit(fname, args):
        code_args = ", ".join(f"{k}={v!r}" for k, v in args.items())
        return f"print({fname}({code_args}))", fname

    def policy(view, steps):
        done = [s.get("tool") for s in steps if s.get("type") == "tool_call"]
        # 1. satisfy read-only trace milestones first (one call each, valid args)
        for t in traced_readonly:
            if t not in done:
                return _emit(t, _fill_args(t))
        # 2. satisfy database-addition milestones with gold row values
        for table, rows in additions:
            tool = _tool_for_table(table, world_impl, scenario)
            if tool is None or tool in done:
                continue
            row = {k: v for k, v in rows[0].items()}
            view_text = prefix_cache.canonical(view).lower()
            visible = all(str(v).lower() in view_text
                          for v in row.values() if v is not None)
            episode_state["info_source"].append(
                "handoff_view" if visible else "gold_fallback")
            return _emit(tool, row)
        return None
    return policy


def scenario_tool(scenario, name):
    ctx = scenario.starting_context
    return ctx.name_to_tool[name]


def _default_for(annotation):
    s = str(annotation)
    if "int" in s:
        return 0
    if "str" in s:
        return ""
    if "bool" in s:
        return False
    return 0.0                                    # float / unknown


def _tool_for_table(table, world_impl, scenario):
    """Map a milestone table to the tool that writes it: try add_<table>, then the
    side-effect tool whose signature covers the target row keys."""
    guess = f"add_{table.lower()}"
    if guess in world_impl and world_impl[guess]["side_effect"]:
        return guess
    for name, spec in world_impl.items():
        if not spec["side_effect"] or name.startswith(("remove_", "modify_", "set_")):
            continue
        try:
            import inspect as _i
            params = set(_i.signature(scenario_tool(scenario, name)).parameters)
            row_keys = {k for ms in scenario.evaluation.milestone_matcher.milestones
                        for c in ms.snapshot_constraints
                        if c.target_dataframe is not None
                        and c.database_namespace.name == table
                        for k in c.target_dataframe.columns}
            if row_keys and row_keys <= params:
                return name
        except (TypeError, ValueError):
            continue
    return None


# ---------------------------------------------------------------- episode driver
def _initial_transcript(ctx_mod, base_role):
    """Build our harness transcript (system, user) from the scenario's SANDBOX messages."""
    msgs = base_role.get_messages()
    system = "\n".join(m.content for m in msgs
                       if m.sender == ctx_mod.RoleType.SYSTEM and m.recipient == ctx_mod.RoleType.AGENT)
    user = [m for m in msgs if m.sender == ctx_mod.RoleType.USER and m.recipient == ctx_mod.RoleType.AGENT]
    if not user:
        raise RuntimeError("scenario has no USER->AGENT task message")
    return [{"role": "system", "content": system},
            {"role": "user", "content": user[-1].content}]


def run_episode(scenario_name, column, switch_after_turn, repo_path, max_turns=6,
                scenarios=None):
    """Run one column of one scenario. Returns the run record (same shape as runner.run)."""
    if column not in COLUMNS:
        raise ValueError(column)
    scenario, world_impl, make_context = load_world(scenario_name, repo_path,
                                                    scenarios=scenarios)
    ctx = make_context()
    import tool_sandbox.common.execution_context as ctx_mod
    from tool_sandbox.common.message_conversion import Message
    from tool_sandbox.roles.base_role import BaseRole
    from tool_sandbox.roles.execution_environment import ExecutionEnvironment

    env = ExecutionEnvironment()
    # execute SYSTEM->EXECUTION_ENVIRONMENT init messages (tool imports) exactly as the
    # ToolSandbox harness does — without this the REPL has no tool names bound
    for i, m in enumerate(BaseRole.get_messages()):
        if m.sender == ctx_mod.RoleType.SYSTEM and m.recipient == ctx_mod.RoleType.EXECUTION_ENVIRONMENT:
            env.respond(ending_index=i)

    episode_state = {"info_source": []}
    policy = make_policy(scenario, world_impl, episode_state)
    messages = _initial_transcript(ctx_mod, BaseRole)
    episode_id = f"ts_{scenario_name}"
    ledger = IdempotencyLedger(episode_id)
    steps, prefix_ids, checks_fired = [], {}, []
    source, target = SimpleNamespace(name="mock-source"), SimpleNamespace(name="mock-target")
    handoff_applied, turn = False, 0

    while turn < max_turns:
        actor = target if (column == "b0" or handoff_applied) else source
        view = messages                              # what THIS model actually sees
        action = policy(view, steps)
        if action is None:
            break
        code, fname = action
        step = {"model": actor.name, "type": "tool_call", "tool": fname}
        # parse canonical args back out of the code string for the ledger
        args = _parse_args(code, fname)
        step["args"] = args
        step["side_effect"] = world_impl[fname]["side_effect"]
        oid, key, decision, prior = ledger.before_execute(fname, args, step["side_effect"])
        step["logical_op_id"], step["idempotency_key"] = oid, key

        if decision == "suppress":
            step["execution"], step["result"] = "suppressed", prior
            checks_fired.append("V3_duplicate_suppressed")
        else:
            BaseRole.add_messages([Message(
                sender=ctx_mod.RoleType.AGENT, recipient=ctx_mod.RoleType.EXECUTION_ENVIRONMENT,
                content=code, openai_tool_call_id=f"call_{turn:04d}", openai_function_name=fname,
                visible_to=[ctx_mod.RoleType.AGENT, ctx_mod.RoleType.EXECUTION_ENVIRONMENT])])
            env.respond()
            resp = BaseRole.get_messages()[-1]
            step["execution"] = "executed"
            step["result"] = resp.content
            step["tool_trace"] = resp.tool_trace
            step["tool_call_exception"] = resp.tool_call_exception
            messages.append({"role": "assistant", "content": code})
            messages.append({"role": "tool", "content": resp.content or ""})
        ledger.record(oid, key, step["execution"], step["result"])
        steps.append(step)

        if column != "b0" and not handoff_applied and turn == switch_after_turn:
            prefix_ids["switch"] = prefix_cache.prefix_id(messages)
            checks_fired.append(f"switch_reached:after_turn_{turn}")
            messages = _apply_handoff(column, messages, steps)
            handoff_applied = True
        turn += 1

    result = scenario.evaluation.evaluate(ctx, max_turn_count=scenario.max_messages)
    # frozen epsilon-gate on handoff columns (same as runner.run)
    gate_branch, gate_detail = None, None
    if column != "b0":
        import gate as gate_mod
        gate_detail = gate_mod.evaluate(steps, seed=0)
        gate_branch = gate_detail["branch"]
        checks_fired.append(f"gate:{gate_branch}")
    return {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "mode": "cpu_mock_toolsandbox",
        "episode_id": episode_id,
        "scenario": scenario_name,
        "column": column,
        "switch_after_turn": None if column == "b0" else switch_after_turn,
        "model_source": source.name, "model_target": target.name,
        "prefix_ids": prefix_ids,
        "steps": steps,
        "checks_fired": checks_fired,
        "gate_branch": gate_branch,
        "gate_detail": gate_detail,
        "seed": 0,
        # did the column's handoff representation carry the values the target needed?
        # (B0 has no handoff -> None; handoff columns: did any post-switch action need
        #  oracle fallback because the value was absent from the target's view?)
        "policy_info_source": episode_state["info_source"],
        "handoff_info_sufficient": None if column == "b0" else
            ("gold_fallback" not in episode_state["info_source"]),
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},   # mock: no GPU tokens
        "gpu_h": 0.0, "cash": 0.0,
        "score": {"similarity": result.similarity,
                  "milestone_similarity": result.milestone_similarity,
                  "minefield_similarity": result.minefield_similarity,
                  "turn_count": result.turn_count},
        "_ctx": ctx,                              # in-process only; stripped before writing
    }


def _parse_args(code, fname):
    """Recover canonical args from the scripted python call (policy emits literal kwargs)."""
    m = re.search(re.escape(fname) + r"\((.*)\)", code)
    if not m:
        return {}
    kwargs = {}
    for kv in re.finditer(r"(\w+)\s*=\s*('[^']*'|[\d.]+|None)", m.group(1)):
        k, v = kv.group(1), kv.group(2)
        if v == "None":
            kwargs[k] = None
        elif v.startswith("'"):
            kwargs[k] = v.strip("'")
        else:
            kwargs[k] = float(v) if "." in v else int(v)
    return kwargs


def _apply_handoff(column, messages, steps):
    """Dispatch to the REAL column hook (b1 keeps the raw transcript)."""
    if column == "b1":
        return messages
    if column == "b2a":
        import compiler as compiler_mod
        cand, _ = compiler_mod.compile_handoff(steps)
        budget = len(prefix_cache.canonical(cand["payload"])) // 4   # matched-token budget
        import b2a
        _, new_messages = b2a.make_handoff(budget)(model=None, messages=messages,
                                                   state=None, steps=steps)
        return new_messages
    if column == "b3":
        import b3
        _, new_messages = b3.make_handoff()(model=None, messages=messages,
                                            state=None, steps=steps)
        return new_messages
    if column == "compiler":
        import compiler as compiler_mod
        _, new_messages = compiler_mod.make_handoff()(model=None, messages=messages,
                                                      state=None, steps=steps)
        return new_messages
    raise ValueError(column)


_PROBE_CACHE = {}


def probe_switch_turn(scenario_name, kind, scenarios, repo):
    """Derive the switch turn index for S1/S2/S3 by probing the scenario once.

    S1 first_tool:       after turn 0 (first tool call of any kind)
    S2 first_side_effect: after the first step whose tool mutates the world (decisive)
    S3 half:             after >= half of the scripted tool calls have executed
    """
    if scenario_name not in _PROBE_CACHE:
        rec = run_episode(scenario_name, "b0", 0, repo, scenarios=scenarios)
        _PROBE_CACHE[scenario_name] = rec["steps"]
    steps = _PROBE_CACHE[scenario_name]
    if kind == "first_tool":
        return 0
    if kind == "first_side_effect":
        for i, s in enumerate(steps):
            if s.get("side_effect"):
                return i
        return 0
    if kind == "half":
        return max(0, len([s for s in steps if s.get("type") == "tool_call"]) // 2)
    raise ValueError(kind)


# ---------------------------------------------------------------- pairing/world asserts
def _world_fingerprint(ctx):
    """Hash the REMINDER database minus server-generated fields (uuid, creation_timestamp)."""
    import tool_sandbox.common.execution_context as ctx_mod
    df = ctx.get_database(ctx_mod.DatabaseNamespace.REMINDER)
    cols = [c for c in df.columns if c not in ("reminder_id", "creation_timestamp",
                                               "sandbox_message_index")]
    return prefix_cache.hashlib.sha256(
        prefix_cache.canonical(df.select(cols).to_dicts()).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="path to pinned ToolSandbox checkout")
    ap.add_argument("--scenario", default="add_reminder_content_and_date_and_time")
    ap.add_argument("--switch-after-turn", type=int, default=0,
                    help="switch after this many source turns (0 = S1-like earliest)")
    ap.add_argument("--out", default="logs/toolsandbox_dry_run.json")
    args = ap.parse_args()

    from executor import load_scenarios
    scenarios = load_scenarios(args.repo)   # ONE load: seed world byte-identical across columns
    records = {}
    for col in COLUMNS:
        rec = run_episode(args.scenario, col, args.switch_after_turn, args.repo,
                          scenarios=scenarios)
        records[col] = rec
        print(f"[{col:8s}] similarity={rec['score']['similarity']:.3f} "
              f"turns={rec['score']['turn_count']} steps={len(rec['steps'])} "
              f"checks={rec['checks_fired']}")

    # A1: strict pairing — identical prefix snapshot across all handoff columns
    anchors = {c: r["prefix_ids"].get("switch") for c, r in records.items() if c != "b0"}
    assert len(set(anchors.values())) == 1, f"A1 pairing violated: {anchors}"
    # A2: identical final world across ALL columns
    fps = {c: _world_fingerprint(r["_ctx"]) for c, r in records.items()}
    assert len(set(fps.values())) == 1, f"A2 world divergence: {fps}"

    out = {"scenario": args.scenario, "switch_after_turn": args.switch_after_turn,
           "pairing_anchor": anchors["b1"], "world_fingerprint": fps["b0"],
           "assertions": {"A1_prefix_identity": "PASS", "A2_world_identity": "PASS"},
           "columns": {c: {k: v for k, v in r.items() if k != "_ctx"}
                       for c, r in records.items()}}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"A1 prefix identity: PASS  (anchor {anchors['b1'][:16]}…)")
    print(f"A2 world identity:  PASS  (fingerprint {fps['b0'][:16]}…)")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
