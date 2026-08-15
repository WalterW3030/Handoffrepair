"""T3 — Column B3: fixed typed state handoff (REAL implementation).

At the switch point a FIXED, hand-written typed template (same fields as the ledger
schema, populated by deterministic rules — no learning, no search) is handed to the
target. Isolates the value of typed STRUCTURE from the compiler's selection/optimization.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ledger as ledger_mod
import prefix_cache

TEMPLATE_FIELDS = ["G", "C", "E", "P", "M", "S", "U"]   # same fields as the ledger schema


def build_typed_state(steps):
    """Populate the fixed template from the trajectory via deterministic extraction."""
    led = ledger_mod.extract(steps)
    return {f: led[f] for f in TEMPLATE_FIELDS}


def make_handoff():
    """Returns the runner's handoff hook (no budget to bind)."""
    def _handoff(model, messages, state, steps):
        typed = build_typed_state(steps)
        new_messages = [messages[0], messages[1],
                        {"role": "assistant",
                         "content": "TYPED STATE:\n" + prefix_cache.canonical(typed)}]
        return model, new_messages
    return _handoff
