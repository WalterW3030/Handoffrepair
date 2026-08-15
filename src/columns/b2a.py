"""T3 — Column B2a: matched-token summary handoff (REAL implementation).

At the switch point the source's trajectory is summarized into natural language;
the target continues from system+user+SUMMARY (not the raw transcript). The summary
token budget is MATCHED to the compiler handoff's token count on the same episode,
so B2a and the compiler differ in WHAT is handed over, not HOW MUCH.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import prefix_cache


def summarize(steps, token_budget):
    """Deterministic extractive summary of tool-call steps, truncated to token_budget."""
    lines = []
    for s in steps:
        if s.get("type") == "tool_call":
            lines.append(f"- called {s.get('tool')} args={prefix_cache.canonical(s.get('args', {}))} "
                         f"result={prefix_cache.canonical(s.get('result', {}))}")
        else:
            lines.append(f"- said: {s.get('content', '')}")
    out, used = [], 0
    for ln in lines:
        t = len(ln) // 4                       # token stub (chars/4), consistent with mock accounting
        if used + t > token_budget:
            break
        out.append(ln); used += t
    return "Trajectory so far:\n" + "\n".join(out)


def make_handoff(token_budget):
    """Bind the matched token budget; returns the runner's handoff hook."""
    def _handoff(model, messages, state, steps):
        summary = summarize(steps, token_budget)
        new_messages = [messages[0], messages[1],                   # system, user
                        {"role": "assistant", "content": summary}]
        return model, new_messages
    return _handoff
