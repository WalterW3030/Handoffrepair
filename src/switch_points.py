"""A7 — Semantic switch-point detection (pilot uses S1-S3; S2 is decisive).

Semantics (configs/switch_points.yaml):
  S1: after the first tool call of ANY kind
  S2: immediately after the first STATE-CHANGING tool call
  S3: after >= half of the episode's expected actions have executed

Detection runs on the steps executed SO FAR during an episode, so the
runner can ask "have we reached the switch point?" after every step.
expected_len is the source script length (known in the mock harness; on
real ToolSandbox episodes it is the planner's expected action count).
"""
import yaml, os

_DEFS = None

def definitions():
    global _DEFS
    if _DEFS is None:
        cfg = os.path.join(os.path.dirname(__file__), "..", "configs", "switch_points.yaml")
        with open(cfg) as f:
            _DEFS = yaml.safe_load(f)
    return _DEFS


def reached(steps, point, expected_len):
    """steps: list of executed step dicts with keys type / side_effect."""
    tool_calls = [i for i, s in enumerate(steps) if s["type"] == "tool_call"]
    if point == "S1":
        return bool(tool_calls) and len(steps) - 1 == tool_calls[0]
    if point == "S2":
        se = [i for i, s in enumerate(steps)
              if s["type"] == "tool_call" and s.get("side_effect")]
        return bool(se) and len(steps) - 1 == se[0]
    if point == "S3":
        half = max(1, expected_len // 2)
        return len(steps) == half
    raise ValueError(f"unknown switch point {point!r} (pilot supports S1-S3)")
