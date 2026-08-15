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
    def __init__(self, name, script, repeat_last_tool=0, fail_first_n=0):
        """repeat_last_tool: after the script ends, re-emit the last tool_call this many
        times (tests duplicate side-effect suppression). fail_first_n: raise TransportError
        on the first n generate() calls (tests transport retry reusing the op-ID)."""
        if not script:
            raise ValueError("script must be non-empty")
        self.name = name
        self.script = list(script)
        self.repeat_last_tool = repeat_last_tool
        self.fail_first_n = fail_first_n
        self._calls = 0
        self._acts = 0          # how many actions THIS model has emitted

    def generate(self, messages, tools=None):
        self._calls += 1
        if self._calls <= self.fail_first_n:
            from runner import TransportError
            raise TransportError(f"injected transport failure {self._calls}")
        # Index THIS model's own script by how many actions it has already taken
        # (NOT the global assistant-turn count) — so a target picking up mid-trajectory
        # starts from the head of its own script.
        k = self._acts
        if k < len(self.script):
            action = dict(self.script[k])
        else:
            # script exhausted: repeat last tool_call if asked, else hold last action
            last_tool = next((a for a in reversed(self.script) if a["type"] == "tool_call"),
                             self.script[-1])
            action = dict(last_tool if self.repeat_last_tool > 0 else self.script[-1])
            if self.repeat_last_tool > 0:
                self.repeat_last_tool -= 1
        self._acts += 1
        return {
            "model": self.name,
            "action": action,
            "usage": {
                # token accounting stub (chars/4); real accounting comes from vLLM on GPU
                "prompt_tokens": len(json.dumps(messages, sort_keys=True)) // 4,
                "completion_tokens": len(json.dumps(action, sort_keys=True)) // 4,
            },
        }
