"""A4 — Column B0: target-from-start. Fresh episode, target model runs all turns.
Upper-bound reference: what the target could do with no handoff at all."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run


def run_b0(episode, source, target, seed, log_path):
    return run(episode, column="b0", switch_point=None,
               source=source, target=target, seed=seed, log_path=log_path)
