"""A2 — Deterministic mock model for CPU harness validation.

Emits scripted actions as a pure function of (script, messages): the k-th
assistant turn returns script[min(k, len-1)]. No RNG — full determinism,
which is exactly what the freeze + strict-pairing requirements need.
On the GPU machine this class is replaced by a vLLM client with the same
generate() signature; nothing downstream changes.

Action dicts:
  {"type": "tool_call", "tool": <name>, "args": {...}}
  {"type": "message",   "content": <str>}     # terminal answer
"""
import json


class MockModel:
    def __init__(self, name, script):
        if not script:
            raise ValueError("script must be non-empty")
        self.name = name
        self.script = list(script)

    def generate(self, messages, tools=None):
        k = sum(1 for m in messages if m.get("role") == "assistant")
        action = dict(self.script[min(k, len(self.script) - 1)])
        return {
            "model": self.name,
            "action": action,
            "usage": {
                # token accounting stub (chars/4); real accounting comes from vLLM on GPU
                "prompt_tokens": len(json.dumps(messages, sort_keys=True)) // 4,
                "completion_tokens": len(json.dumps(action, sort_keys=True)) // 4,
            },
        }
