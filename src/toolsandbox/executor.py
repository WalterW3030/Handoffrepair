"""T-d — Real ToolSandbox executor wiring (verified on CPU; the same code drives the GPU run).

Loads a selected self-contained scenario (from configs/episodes_pilot.yaml, produced by
select_scenarios.py at Day 0) against the pinned ToolSandbox checkout
(commit 165848b9a78cead7ca7fe7c89c688b58e6501219) and exposes its tools as a world_impl
with the {tool: {"side_effect": bool, "fn": callable}} shape used by src/runner.py.

Key facts about the pinned commit (discovered by CPU dry-run, Day 0):
  * tools are plain functions decorated @register_as_tool; they mutate the world through
    get_current_context().add_to_database / update_database / remove_from_database
    (instance methods of ExecutionContext at this commit — NOT module-level functions);
  * side_effect flags are derived by static source inspection for those three mutators;
  * tool execution goes through the real ExecutionEnvironment role, which runs agent
    messages (Python source) in a REPL and writes tool_trace rows to the SANDBOX table;
  * scoring is scenario.evaluation.evaluate(execution_context, max_turn_count) — the
    milestone/minefield DAG, deterministic, no LLM judge.
"""
import inspect, os, sys, yaml

PINNED_COMMIT = "165848b9a78cead7ca7fe7c89c688b58e6501219"

_MUTATORS = ("add_to_database", "update_database", "remove_from_database")


def tool_has_side_effect(fn):
    """A tool is state-changing iff its source calls a database mutator."""
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        return True                      # unknown => treat as state-changing (safe)
    return any(m in src for m in _MUTATORS)


def load_scenarios(repo_path):
    """Import ToolSandbox from the pinned checkout and return {name: Scenario}."""
    if repo_path not in sys.path:
        sys.path.insert(0, repo_path)
    from tool_sandbox.common.tool_discovery import ToolBackend
    from tool_sandbox.scenarios import named_scenarios
    backend = getattr(ToolBackend, "HERMES", ToolBackend.DEFAULT)   # HERMES absent at pin
    return named_scenarios(preferred_tool_backend=backend)


def load_world(scenario_name, repo_path, scenarios=None):
    """Instantiate a scenario and adapt its tools to our world_impl shape.

    Returns (scenario, world_impl, make_context) where make_context() yields a FRESH
    ExecutionContext copy (ExecutionContext.from_dict(starting_context.to_dict())) —
    one per episode run, so columns never share mutable world state.

    Pass a pre-loaded `scenarios` dict when running several columns of the SAME episode:
    scenario construction is wall-clock dependent (seed timestamps derive from now()),
    so one shared load keeps the seed world byte-identical across columns — required
    for the strict-pairing world-state comparison.
    """
    scenarios = scenarios if scenarios is not None else load_scenarios(repo_path)
    if scenario_name not in scenarios:
        raise KeyError(f"scenario {scenario_name!r} not in pinned ToolSandbox checkout")
    scenario = scenarios[scenario_name]
    from tool_sandbox.common.execution_context import ExecutionContext, set_current_context

    def make_context():
        ctx = ExecutionContext.from_dict(scenario.starting_context.to_dict())
        set_current_context(ctx)
        return ctx

    ctx = make_context()
    world_impl = {}
    for name, fn in ctx.name_to_tool.items():
        def _make(f):
            def _call(_state, args):     # runner world_impl signature: fn(state, args)
                return f(**args)
            return _call
        world_impl[name] = {"side_effect": tool_has_side_effect(fn), "fn": _make(fn)}
    return scenario, world_impl, make_context


def selected_episodes():
    cfg = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "episodes_pilot.yaml")
    if not os.path.exists(cfg):
        raise FileNotFoundError("episodes_pilot.yaml not generated yet — run select_scenarios.py at Day 0")
    with open(cfg) as f:
        return yaml.safe_load(f)["pilot_episode_set"]
