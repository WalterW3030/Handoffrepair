"""A9 — End-to-end CPU smoke dry run: 5 episodes x (B0 + B1 x S1-S3).

Proves the whole pipeline before a single GPU dollar is spent:
  episode runner, prefix pairing, switch injection, columns B0/B1,
  DAG scoring, idempotency keys, append-only logging.

Asserts:
  1. strict pairing — same (episode, switch) re-run gives identical prefix ID
  2. every log record schema-complete
  3. append-only — log length only grows
Writes: logs/smoke_log.jsonl, smoke/summary.json
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "columns"))
sys.path.insert(0, os.path.join(ROOT, "src", "scoring"))

import mock_model, prefix_cache, logging_
from columns import b0, b1
from scoring import synthetic_episodes as se

LOG = os.path.join(ROOT, "logs", "smoke_log.jsonl")
SUMMARY = os.path.join(ROOT, "smoke", "summary.json")
SEED = 1


def main():
    episodes = se.make_smoke_episodes()
    assert [e["episode_id"] for e in episodes] == [
        "smoke_morning_1", "smoke_morning_2", "smoke_event_1",
        "smoke_event_2", "smoke_event_3"], "episode set drifted from configs/episodes.yaml"

    n_before = len(logging_.read_log(LOG))
    results = []

    for ep in episodes:
        src = lambda: mock_model.MockModel("mock-source", ep["source_script"])
        tgt = lambda: mock_model.MockModel("mock-target", ep["target_script"])

        r0 = b0.run_b0(ep, src(), tgt(), SEED, LOG)
        results.append(r0)

        for sp in ("S1", "S2", "S3"):
            r1 = b1.run_b1(ep, sp, src(), tgt(), SEED, LOG)
            results.append(r1)

            # strict pairing check: re-run identical (episode, switch) -> identical prefix
            r2 = b1.run_b1(ep, sp, src(), tgt(), SEED, None)
            prefix_cache.assert_paired([r1["prefix_ids"]["switch"], r2["prefix_ids"]["switch"]])

    # append-only + schema checks
    records = logging_.read_log(LOG)
    assert len(records) == n_before + len(results), "append-only violated"
    for r in records:
        assert all(k in r for k in logging_.REQUIRED_FIELDS), "schema incomplete"

    summary = {
        "episodes": len(episodes),
        "runs": len(results),
        "pairing_checks": len(episodes) * 3,
        "by_column": {},
        "table": [
            {"episode": r["episode_id"], "column": r["column"],
             "switch": r["switch_point"], "raw": r["score"]["raw"],
             "success": r["score"]["success"], "minefields": r["score"]["minefields_hit"]}
            for r in results
        ],
    }
    for col in ("b0", "b1"):
        rs = [r for r in results if r["column"] == col]
        summary["by_column"][col] = {
            "mean_raw": round(sum(r["score"]["raw"] for r in rs) / len(rs), 4),
            "success_rate": round(sum(r["score"]["success"] for r in rs) / len(rs), 4),
            "minefield_hits": sum(len(r["score"]["minefields_hit"]) for r in rs),
        }
    with open(SUMMARY, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary["by_column"], indent=2))
    print(f"\nOK: {len(results)} runs, {len(episodes)*3} pairing checks passed, "
          f"log appended {len(records)-n_before} records -> {LOG}")


if __name__ == "__main__":
    main()
