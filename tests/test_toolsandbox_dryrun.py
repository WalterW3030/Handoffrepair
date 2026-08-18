"""T-d — Real ToolSandbox dry-run tests (advisor: "one real ToolSandbox dry-run through
every implemented column", discoverable test output).

Skipped unless the pinned ToolSandbox checkout is present (TOOLSANDBOX_REPO env or
/opt/ToolSandbox). On the GPU machine and in clean-environment verification with the
checkout available, these run for real.
"""
import os, sys
import pytest

REPO = os.environ.get("TOOLSANDBOX_REPO", "/opt/ToolSandbox")
pytestmark = pytest.mark.skipif(
    not os.path.isdir(os.path.join(REPO, "tool_sandbox")),
    reason="pinned ToolSandbox checkout not present")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "toolsandbox"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "columns"))

SCENARIO = "add_reminder_content_and_date_and_time"


@pytest.fixture(scope="module")
def records():
    import dry_run
    from executor import load_scenarios
    scenarios = load_scenarios(REPO)
    return {c: dry_run.run_episode(SCENARIO, c, 0, REPO, scenarios=scenarios, seed=1)
            for c in dry_run.COLUMNS}


def test_all_columns_score_perfect_with_oracle_policy(records):
    for col, rec in records.items():
        assert rec["score"]["similarity"] == 1.0, (col, rec["score"])
        assert rec["score"]["minefield_similarity"] == 0


def test_strict_pairing_prefix_identity(records):
    anchors = {c: r["prefix_ids"].get("switch") for c, r in records.items() if c != "b0"}
    assert len(set(anchors.values())) == 1 and anchors["b1"]


def test_world_identity_across_columns(records):
    import dry_run
    fps = {c: dry_run._world_fingerprint(r["_ctx"]) for c, r in records.items()}
    assert len(set(fps.values())) == 1


def test_handoff_information_discrimination(records):
    """B1 raw transcript carries the resolved values; B2a/B3/compiler drop tool results."""
    assert records["b1"]["handoff_info_sufficient"] is True
    for col in ("b2a", "b3", "compiler"):
        assert records[col]["handoff_info_sufficient"] is False


def test_record_schema_matches_frozen_log(records):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    import logging_
    for rec in records.values():
        r = {k: v for k, v in rec.items() if k != "_ctx"}
        r.setdefault("switch_point", None)
        missing = [f for f in logging_.REQUIRED_FIELDS if f not in r]
        assert not missing, missing
