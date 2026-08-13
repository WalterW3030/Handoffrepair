"""A8/P2 — Gemma-3-27B tool-call shim.

Gemma 3 has no dedicated function-calling tokens. This shim implements tool
calling as prompt-based JSON, with vLLM structured outputs (guided JSON
schema) guaranteeing every response is a PARSEABLE call — as the vLLM docs
put it, parseable, not necessarily high-quality. That quality gap is real
signal: it is recorded in Gemma's capability manifest as interface distance,
which is part of the held-out-pair stress the pilot measures.

No manual per-call fixing at runtime (Rule 26): if a call fails schema
validation after MAX_RETRIES deterministic re-prompts, the episode is logged
as a shim failure and continues with an empty turn — the failure is data,
not a bug to be hand-patched.
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


class GemmaToolShim:
    """Drop-in replacement with the same generate(messages, tools) signature
    as MockModel / the vLLM hermes client, so the runner never knows which
    model interface it is talking to (manifest records the difference)."""

    def __init__(self, client, model_name="google/gemma-3-27b-it"):
        self.client = client          # openai-compatible vLLM client
        self.name = model_name

    def generate(self, messages, tools=None):
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        prompt = PROMPT_TEMPLATE.format(
            schema=json.dumps(TOOL_CALL_SCHEMA),
            tools=json.dumps(tools or []),
            transcript=transcript,
        )
        for attempt in range(MAX_RETRIES + 1):
            resp = self.client.chat.completions.create(
                model=self.name,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"guided_json": TOOL_CALL_SCHEMA},
                temperature=0.0,
            )
            try:
                action = json.loads(resp.choices[0].message.content)
                u = resp.usage
                usage = (u.model_dump() if hasattr(u, "model_dump")
                         else {k: getattr(u, k, 0) for k in ("prompt_tokens", "completion_tokens")})
                return {"model": self.name, "action": action, "usage": usage}
            except (json.JSONDecodeError, AttributeError):
                continue                       # deterministic re-prompt
        # exhausted: log as shim failure, emit empty terminal turn
        return {"model": self.name,
                "action": {"type": "message", "content": "[shim_failure]"},
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
