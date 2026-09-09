"""GPU-mode policy + tool schemas + grounded user simulator (2026-09-08, M28 follow-up).

The mock path drives episodes with a scripted oracle policy. This module is the real
one: the served model — through UniformToolShim (the frozen, T2-validated extraction
layer) — decides every action from the column's message view. No gold values are ever
shown to the model; every arg it emits is model-generated and recorded as such.

Design rules honored here:
  - R0:  the episode loop in dry_run is UNCHANGED except the policy source; world
         execution (ToolSandbox ExecutionEnvironment) is byte-identical.
  - Rule 26: no manual per-call fixing. A shim_failure is data; the episode ends with
         an empty terminal turn, as the shim's contract specifies.
  - Info-source honesty: mock labels args 'handoff_view'/'gold_fallback'; GPU mode
         labels every action 'model_generated' — the model IS the info-sufficiency
         test, so the label carries no oracle meaning.
"""
import inspect
import json


# ----------------------------------------------------------------- tool schemas
def tool_schemas(scenario, world_impl, repo_path=None):
    """Build shim-consumable JSON schemas for every tool the scenario exposes.

    Parameters come from inspecting the real ToolSandbox tool functions — the same
    source the ExecutionEnvironment binds. Types are mapped from Python annotations
    to JSON Schema types; unannotated params become permissive strings.
    """
    from dry_run import scenario_tool  # same module dir (src/toolsandbox on sys.path)
    schemas = []
    for name in sorted(world_impl):
        try:
            fn = scenario_tool(scenario, name)
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError, KeyError):
            continue
        props, required = {}, []
        for p, prm in params.items():
            ann = str(prm.annotation)
            if "int" in ann:
                t = "integer"
            elif "bool" in ann:
                t = "boolean"
            elif "float" in ann or "number" in ann:
                t = "number"
            else:
                t = "string"
            props[p] = {"type": t}
            if prm.default is inspect.Parameter.empty:
                required.append(p)
        schemas.append({
            "name": name,
            "description": (inspect.getdoc(fn) or "").split("\n")[0] if fn else "",
            "parameters": {"type": "object", "properties": props, "required": required},
            "side_effect": bool(world_impl[name]["side_effect"]),
        })
    return schemas


# ------------------------------------------------------------- action -> code
def action_to_code(tool, args):
    """Same executable shape the mock policy emits: print(fname(k=v, ...)) — the
    ToolSandbox REPL binds tool functions and the harness captures the print.
    Returns (code, fname) like the mock policy's _emit."""
    code_args = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
    return f"print({tool}({code_args}))", tool


class GpuPolicy:
    """Callable policy(view, steps) driven by a served model via the shim.

    Returns:
      (code, fname)          — a tool call to execute
      ("__MESSAGE__", text)  — the model chose to speak to the user instead
      None                   — model signalled episode end (stop)
    Accumulates token usage across calls for the run record.
    """

    def __init__(self, tools, episode_state):
        self.tools = tools
        self.state = episode_state
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def for_actor(self, shim):
        """Bind one actor's shim for the upcoming turn (source pre-switch, target post)."""
        def _policy(view, steps):
            resp = shim.generate(view, self.tools)
            u = resp.get("usage") or {}
            self.usage["prompt_tokens"] += u.get("prompt_tokens", 0)
            self.usage["completion_tokens"] += u.get("completion_tokens", 0)
            action = resp["action"]
            self.state["info_source"].append("model_generated")
            self.state.setdefault("shim_failures", 0)
            if action.get("content") == "[shim_failure]":
                self.state["shim_failures"] += 1
                return None                       # empty terminal turn (shim contract)
            if action.get("type") == "message":
                return ("__MESSAGE__", action.get("content", ""))
            return action_to_code(action.get("tool", ""), action.get("args") or {})
        return _policy


# ------------------------------------------------------- grounded user simulator
USER_SIM_PROMPT = """You are simulating the user in a tool-use episode. The agent may
ask you for information. Answer ONLY from the user data below — give exactly the
values asked for, concisely, in one message. If the agent's message needs no answer
(it is a confirmation or closing), reply with exactly: DONE.

User data (the sandbox database at episode start):
{grounding}
"""


def make_grounded_user_sim(client, model_name, scenario):
    """User simulator whose answers are grounded in the scenario's sandbox DB —
    same information source the mock policy reads, but real generation (seed 101
    per configs/seeds.yaml; decoding temperature is 0.0 so it is deterministic
    up to serving nondeterminism)."""
    import tool_sandbox.common.execution_context as _ec
    try:
        rows = scenario.starting_context.get_database(_ec.DatabaseNamespace.SANDBOX).to_dicts()
    except Exception:
        rows = []
    grounding = json.dumps(rows, default=str)[:4000]

    def respond(conversation):
        prompt = ([{"role": "system", "content": USER_SIM_PROMPT.format(grounding=grounding)}]
                  + conversation)
        out = client.chat.completions.create(model=model_name, messages=prompt,
                                             temperature=0.0, max_tokens=256)
        return out.choices[0].message.content or "DONE"

    return respond
