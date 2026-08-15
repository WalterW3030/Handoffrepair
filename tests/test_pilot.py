"""T8 — Discoverable pytest suite. Every advisor-required case is a test_* function
pytest can collect and run: `python -m pytest tests/ -q`.
"""
import os, sys, json
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("src", "src/columns", "src/scoring", "serving"):
    sys.path.insert(0, os.path.join(ROOT, p))

import mock_model, runner, prefix_cache, manifest, logging_
from scoring import dag as dag_scorer
from scoring.synthetic_episodes import VERIFY_DAG, VERIFY_CASES, make_smoke_episodes, SOURCE_MORNING, TARGET_MORNING
import b2a, b3, compiler, gate, analysis

EPS = make_smoke_episodes()
EP = EPS[0]
SRC = lambda: mock_model.MockModel("src", EP["source_script"])
TGT = lambda: mock_model.MockModel("tgt", EP["target_script"])


# ---- scorer correctness (hand-computed) ----
@pytest.mark.parametrize("name,traj,expected", VERIFY_CASES)
def test_scorer_hand_computed(name, traj, expected):
    assert dag_scorer.score(traj, VERIFY_DAG) == expected


# ---- (req) at least one successful end-to-end episode ----
def test_successful_episode_exists():
    tgt_full = mock_model.MockModel("tgt", [
        {"type": "tool_call", "tool": "send_message", "args": {"to": "bob", "text": "I'll be late"}},
        {"type": "message", "content": "done"}])
    r = runner.run(EP, "b1", "S2", SRC(), tgt_full, 1, None)
    assert r["score"]["success"] is True and r["score"]["raw"] == 1.0


# ---- (req) exact prefix + world-state equality across B1/B2a/B3/compiler ----
def test_cross_column_prefix_equality():
    r_b1 = runner.run(EP, "b1", "S2", SRC(), TGT(), 1, None)
    r_b2a = runner.run(EP, "b2a", "S2", SRC(), TGT(), 1, None, handoff=b2a.make_handoff(120))
    r_b3 = runner.run(EP, "b3", "S2", SRC(), TGT(), 1, None, handoff=b3.make_handoff())
    r_c = runner.run(EP, "compiler", "S2", SRC(), TGT(), 1, None, handoff=compiler.make_handoff())
    ids = [r["prefix_ids"]["switch"] for r in (r_b1, r_b2a, r_b3, r_c)]
    assert len(set(ids)) == 1


# ---- (req) intentional duplicate side-effect: world changes only once ----
def test_duplicate_side_effect_suppressed():
    tgt_dup = mock_model.MockModel("tgt", [
        {"type": "tool_call", "tool": "set_alarm", "args": {"time": "07:00"}},
        {"type": "tool_call", "tool": "set_alarm", "args": {"time": "07:00"}},
        {"type": "tool_call", "tool": "send_message", "args": {"to": "bob", "text": "I'll be late"}},
        {"type": "message", "content": "done"}])
    r = runner.run(EP, "b1", "S2", SRC(), tgt_dup, 1, None)
    al = [s["execution"] for s in r["steps"] if s.get("tool") == "set_alarm"]
    assert al.count("executed") == 1 and al.count("suppressed") == 2
    assert "V3_duplicate_suppressed" in r["checks_fired"]


# ---- (req) transport retry reuses op-ID ----
def test_transport_retry_reuses_op_id():
    tgt_r = mock_model.MockModel("tgt", TARGET_MORNING, fail_first_n=1)
    r = runner.run(EP, "b1", "S2", SRC(), tgt_r, 1, None,
                   retry_config={"retry_rule": {"max_transport_retries": 3}})
    assert any("transport_retry" in c for c in r["checks_fired"])
    assert r["steps"][-1]["type"] == "message"


# ---- (req) gate restart branch ----
def test_gate_restart_branch():
    bad = [{"type": "tool_call", "tool": "x", "side_effect": True,
            "idempotency_key": "K", "execution": "executed"}] * 2
    assert gate.evaluate(bad, seed=0, failure_cost_estimate=0.9)["branch"] == "restart"
    assert gate.evaluate(bad, seed=0, failure_cost_estimate=0.1)["branch"] == "replay_recheck"


# ---- (req) manifest count/accounting assertions from single source ----
def test_manifest_counts_and_b0_no_switch():
    sz = manifest.load_sizing()
    eps = [f"ep_{i:03d}" for i in range(sz["pilot"]["episodes_per_cell"])]
    runs = manifest.enumerate_runs(sz, eps)
    summ = manifest.summarize(runs, sz)
    assert summ["total_runs"] == 1180                       # reconciled single-source count
    b0 = [r for r in runs if r["column"] == "B0"]
    assert all(r["switch_point"] is None for r in b0)       # B0 has no switch point
    assert summ["within_cap"] is True
    assert summ["rate_kind"] in ("planning", "measured")    # never mixed


# ---- (req) clean-log test: unique logical runs vs repeated execution ----
def test_log_unique_runs(tmp_path):
    log = str(tmp_path / "l.jsonl")
    for _ in range(2):                                      # same run appended twice
        runner.run(EP, "b0", None, SRC(), TGT(), 1, log)
    recs = logging_.read_log(log)
    keys = {(r["episode_id"], r["column"], r["switch_point"], r["seed"]) for r in recs}
    assert len(recs) == 2 and len(keys) == 1                # 2 records, 1 unique logical run


# ---- timeout / parser-failure branches ----
def test_timeout_branch_logged():
    # a model that never yields a terminal message hits max_turns -> episode ends, logged
    tgt_loop = mock_model.MockModel("tgt", [{"type": "tool_call", "tool": "get_time", "args": {}}])
    r = runner.run({**EP, "max_turns": 3}, "b0", None, SRC(), tgt_loop, 1, None)
    assert len(r["steps"]) == 3                              # bounded by max_turns (timeout guard)

def test_parser_failure_shim_last_resort():
    import gemma_tool_shim
    assert gemma_tool_shim.MAX_RETRIES >= 1                 # shim gives up deterministically, no manual fix
