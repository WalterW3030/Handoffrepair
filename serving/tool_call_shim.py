"""Uniform tool-call shim — PRIMARY extraction layer for ALL pilot models.

User decision 2026-08-29 (choice 2-C): no engine-native tool parser
(hermes / llama3_json / gemma4) is used anywhere in the pilot. Every model —
Qwen3-32B, Qwen3-8B, Qwen3-30B-A3B-Instruct-2507, gemma-4-31B-it — goes through
this shim, giving the experiment a single, frozen, owned extraction layer:

  * the runner formats the tool schemas into the prompt (PROMPT_TEMPLATE),
  * vLLM guided-JSON (structured outputs) guarantees a PARSEABLE response,
  * the shim validates against TOOL_CALL_SCHEMA and returns a normalized action.

Interface distance vs native tool calling is real signal, not noise: it is
recorded in each model's capability manifest and applies identically to all
four models, so the calibrated-pair comparison stays internally valid.

Supersedes the old gemma_endpoint waterfall (vLLM gemma4 parser -> sglang
-> shim) which is RETIRED as of 2026-08-29; the frozen probe gate now applies
to this shim for every model (docs/NEW_PARAMETER_VALIDATION.md T2).

No manual per-call fixing at runtime (Rule 26): if a call fails schema
validation after MAX_RETRIES deterministic re-prompts, the episode is logged
as a shim failure and continues with an empty turn — the failure is data,
not a bug to be hand-patched.

Known limitation (recorded at design time): guided_json constrains syntax, not
argument quality; T2's 20-case battery per model measures exactly that gap.
"""
import json

TOOL_CALL_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"enum": ["tool_call", "message"]},
        "tool": {"type": "string"},
        "args": {"type": "object"},
        "content": {"type": "string"},
    },
    "required": ["type"],
}
MAX_RETRIES = 2

PROMPT_TEMPLATE = """You are continuing an agent trajectory. You MUST respond with a single
JSON object matching this schema:
{schema}

Available tools:
{tools}

Transcript so far:
{transcript}

Respond with the JSON object only."""


class UniformToolShim:
    """Single tool-call interface for every pilot model. Same
    generate(messages, tools) signature as MockModel / the vLLM client, so the
    runner never knows which model it is talking to (the manifest records the
    difference)."""

    def __init__(self, client, model_name):
        self.client = client          # openai-compatible vLLM client
        self.name = model_name

    def generate(self, messages, tools=None):
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        prompt = PROMPT_TEMPLATE.format(
            schema=json.dumps(TOOL_CALL_SCHEMA),
            tools=json.dumps(tools or []),
            transcript=transcript,
        )
        last_raw = ""
        for attempt in range(MAX_RETRIES + 1):
            resp = self.client.chat.completions.create(
                model=self.name,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"guided_json": TOOL_CALL_SCHEMA},
                temperature=0.0,
            )
            try:
                last_raw = resp.choices[0].message.content or ""
                action = json.loads(last_raw)
                if action.get("type") not in ("tool_call", "message"):
                    raise ValueError("bad action type")
                if action["type"] == "tool_call" and "tool" not in action:
                    raise ValueError("tool_call without tool name")
                u = resp.usage
                usage = (u.model_dump() if hasattr(u, "model_dump")
                         else {k: getattr(u, k, 0) for k in ("prompt_tokens", "completion_tokens")})
                return {"model": self.name, "action": action, "usage": usage}
            except (json.JSONDecodeError, AttributeError, ValueError):
                continue                       # deterministic re-prompt
        # exhausted: log as shim failure, emit empty terminal turn.
        # Attach last_raw so the T2 gate / logs can diagnose WHY it failed (M23).
        return {"model": self.name,
                "action": {"type": "message", "content": "[shim_failure]"},
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                "last_raw": last_raw[:500]}


class GemmaToolShim(UniformToolShim):
    """Backward-compatible alias (pre-2026-08-29 call sites)."""

    def __init__(self, client, model_name="google/gemma-4-31B-it"):
        super().__init__(client, model_name)
