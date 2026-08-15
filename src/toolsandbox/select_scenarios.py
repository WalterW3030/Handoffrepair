"""A6 — P3 scenario selector. Runs ON THE GPU MACHINE at Day 0 (needs ToolSandbox deps).

P3 restriction (advisor reproducibility requirement):
  keep only self-contained scenarios — exclude any scenario whose tool set
  touches rapid_api_search_tools (external web services: search_stock,
  search_lat_lon). Score via milestone/minefield DAG only; user simulator
  is replaced by a LOCAL model with the fixed seed from configs/seeds.yaml
  (ToolSandbox's default user simulator is an external OpenAI API role).

Pinned upstream commit: 165848b9a78cead7ca7fe7c89c688b58e6501219 (2025-11-06).

Usage:
  python select_scenarios.py --repo /path/to/ToolSandbox --out configs/episodes_pilot.yaml
"""
import argparse, sys, yaml

BANNED_NAMESPACE = "rapid_api_search_tools"
# The allow list carries BARE tool names (no namespace prefix), verified against
# tool_sandbox/tools/rapid_api_search_tools.py at the pinned commit: the external
# web-service tools are exactly these two.
BANNED_TOOLS = {"search_stock", "search_lat_lon"}
KEEP_CATEGORIES = {"MULTIPLE_TOOL_CALL", "MULTIPLE_USER_TURN"}   # pilot needs stateful multi-turn


def scenario_tool_names(scenario):
    names = set()
    ctx = getattr(scenario, "starting_context", None) or getattr(scenario, "execution_context", None)
    for attr in ("tool_allow_list", "tool_allowlist", "available_tools"):
        lst = getattr(ctx, attr, None) or getattr(scenario, attr, None)
        if lst:
            names.update(lst)
    if not names:                                   # fallback: scan repr
        rep = repr(scenario)
        for ns in ("contact", "messaging", "reminder", "setting", "user_tools",
                   "utilities", BANNED_NAMESPACE):
            if ns in rep:
                names.add(ns)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sys.path.insert(0, args.repo)

    from tool_sandbox.common.tool_discovery import ToolBackend
    from tool_sandbox.scenarios.multiple_tool_call_scenarios import named_multiple_tool_call_scenarios
    from tool_sandbox.scenarios.multiple_user_turn_scenarios import named_multiple_user_turn_scenarios

    # Pinned commit 165848b exposes ONLY ToolBackend.DEFAULT (no HERMES member yet).
    backend = getattr(ToolBackend, "HERMES", ToolBackend.DEFAULT)
    kept, dropped = [], []
    for registry in (named_multiple_tool_call_scenarios, named_multiple_user_turn_scenarios):
        for name, scenario in registry(preferred_tool_backend=backend).items():
            tools = scenario_tool_names(scenario)
            banned = tools & BANNED_TOOLS or {t for t in tools if BANNED_NAMESPACE in t}
            (dropped if banned else kept).append(name)

    with open(args.out, "w") as f:
        yaml.safe_dump({
            "pinned_commit": "165848b9a78cead7ca7fe7c89c688b58e6501219",
            "pilot_episode_set": sorted(kept),
            "excluded_external_service": sorted(dropped),
            "user_simulator": {"type": "local_model", "seed": 101},
            "scoring": "milestone_minefield_dag_only",
        }, f, sort_keys=False)
    print(f"kept {len(kept)} self-contained scenarios; excluded {len(dropped)} external-service ones")
    print("kept:", sorted(kept))


if __name__ == "__main__":
    main()
