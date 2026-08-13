"""A5 — Scorer verification against hand-computed expected values."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scoring"))

from scoring import dag
from scoring.synthetic_episodes import VERIFY_DAG, VERIFY_CASES


def run():
    failures = []
    for name, trajectory, expected in VERIFY_CASES:
        got = dag.score(trajectory, VERIFY_DAG)
        if got != expected:
            failures.append((name, expected, got))
        print(f"{'PASS' if got == expected else 'FAIL'}  {name}: {got}")
    if failures:
        for name, exp, got in failures:
            print(f"\nMISMATCH {name}:\n  expected {exp}\n  got      {got}")
        sys.exit(1)
    print("\nAll scorer verification cases passed.")


if __name__ == "__main__":
    run()
