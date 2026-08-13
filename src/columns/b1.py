"""A4 — Column B1: raw switch. Source runs to the switch point; target
continues from the identical cached prefix with the transcript concatenated.
No state/contract repair of any kind — the naive-handoff baseline."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runner import run


def run_b1(episode, switch_point, source, target, seed, log_path):
    return run(episode, column="b1", switch_point=switch_point,
               source=source, target=target, seed=seed, log_path=log_path)
