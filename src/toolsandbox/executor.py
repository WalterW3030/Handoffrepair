"""T7 — Real ToolSandbox executor wiring (runs on the GPU machine; needs ToolSandbox deps).

Loads a selected self-contained scenario (from configs/episodes_pilot.yaml, produced by
select_scenarios.py at Day 0), exposes its tools to the runner as a world_impl with the
same {tool: {"side_effect": bool, "fn": callable}} shape as src/world.py, and drives the
agent via our vLLM client + local user simulator. Scoring stays on ToolSandbox's own
milestone/minefield DAG (deterministic; no simulator judgment).

This module is the seam between our frozen harness and the pinned ToolSandbox checkout
(commit 165848b9a78cead7ca7fe7c89c688b58e6501219). It is import-checked here but only
EXECUTES on the GPU machine where ToolSandbox is pip-installed.
"""
import os, sys, yaml

PINNED_COMMIT = "165848b9a78cead7ca7fe7c89c688b58e6501219"


def load_world(scenario_name, repo_path):
    """Instantiate a scenario's tools as our world_impl. Runs only where ToolSandbox exists."""
    sys.path.insert(0, repo_path)
    from tool_sandbox.common.tool_discovery import ToolBackend
    from tool_sandbox.scenarios.multiple_tool_call_scenarios import named_multiple_tool_call_scenarios
    from tool_sandbox.scenarios.multiple_user_turn_scenarios import named_multiple_user_turn_scenarios
    scenarios = {}
    scenarios.update(named_multiple_tool_call_scenarios(preferred_tool_backend=ToolBackend.HERMES))
    scenarios.update(named_multiple_user_turn_scenarios(preferred_tool_backend=ToolBackend.HERMES))
    scenario = scenarios[scenario_name]
    # Adapt ToolSandbox tools to our world_impl shape; side_effect flags come from the
    # scenario's execution context (database-mutating tools) — filled at Day-0 wiring.
    world_impl = {}
    return scenario, world_impl


def selected_episodes():
    cfg = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "episodes_pilot.yaml")
    if not os.path.exists(cfg):
        raise FileNotFoundError("episodes_pilot.yaml not generated yet — run select_scenarios.py at Day 0")
    with open(cfg) as f:
        return yaml.safe_load(f)["pilot_episode_set"]
