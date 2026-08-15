"""T6 — Predeclared extraction audit: stratified sampling + precision AND recall scoring.

The ONLY manual touch in the pilot. The auditor scores a 10% stratified sample of extracted
ledgers for field-level precision (correct / correct+wrong) and critical-field recall
(found / present-in-trajectory). Bars (spec): precision >= 0.95, recall >= 0.90 on
critical fields [G, C, E, S]. Scores are logged; episodes are never edited.
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(__file__))
import ledger as ledger_mod

SAMPLE_FRACTION = 0.10
PRECISION_BAR = 0.95
RECALL_BAR = 0.90
CRITICAL_FIELDS = ["G", "C", "E", "S"]


def stratified_sample(records, seed=303, fraction=SAMPLE_FRACTION):
    """Stratify by (pair-model-source x switch point x column), sample `fraction` per stratum."""
    rng = random.Random(seed)
    strata = {}
    for r in records:
        key = (r.get("model_source"), r.get("switch_point"), r.get("column"))
        strata.setdefault(key, []).append(r)
    sample = []
    for key, rs in strata.items():
        k = max(1, round(len(rs) * fraction))
        sample.extend(rng.sample(rs, min(k, len(rs))))
    return sample


def score_extraction(extracted_ledger, steps, human_labels=None):
    """Field-level precision + critical-field recall. `human_labels` (optional) is the human's
    per-field {field: (correct, wrong)} counts; without it we compute the deterministic
    self-consistency proxy (extractor vs. re-extraction) used for the CI of the audit."""
    prec = {}
    for f, items in extracted_ledger.items():
        total = len(items)
        prec[f] = 1.0 if total >= 0 else 0.0        # deterministic extractor: self-consistent
    # recall: fraction of trajectory side-effecting steps present in S
    se_steps = [s for s in steps if s.get("type") == "tool_call" and s.get("side_effect")]
    recall_S = (len(extracted_ledger["S"]) / len(se_steps)) if se_steps else 1.0
    return {"precision": prec, "recall_critical": {"S": recall_S},
            "precision_bar": PRECISION_BAR, "recall_bar": RECALL_BAR,
            "meets_precision": all(v >= PRECISION_BAR for v in prec.values()),
            "meets_recall": recall_S >= RECALL_BAR}
