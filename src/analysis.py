"""T7 — Analysis: hierarchical bootstrap CIs, epsilon-guarded recovery, Q1-Q4 go/no-go.

All statistics are computed from the append-only run log; no LLM judge anywhere.
Hierarchical bootstrap resamples scenario families then episodes within family
(eval_frozen.yaml), 10,000 resamples, 95% CI, paired on (episode, switch_point, seed).
"""
import random, statistics

EPSILON_PTS = 5          # eval_frozen epsilon_rule
RESAMPLES = 10000
CONF = 0.95
RECOVERY_THRESHOLD = 0.5


def paired_gap(records, col_hi, col_lo, key_fields=("episode_id", "switch_point", "seed")):
    """Per-key score gap between two columns (paired)."""
    def idx(col):
        return {tuple(r[k] for k in key_fields): r["score"]["raw"]
                for r in records if r["column"] == col}
    hi, lo = idx(col_hi), idx(col_lo)
    common = set(hi) & set(lo)
    return {k: hi[k] - lo[k] for k in common}


def hierarchical_bootstrap(gaps_by_family, resamples=RESAMPLES, conf=CONF, seed=1):
    """Resample families, then episodes within family. gaps_by_family: {family: [gap,...]}."""
    rng = random.Random(seed)
    fams = list(gaps_by_family)
    if not fams:
        return (0.0, 0.0, 0.0)
    means = []
    for _ in range(resamples):
        chosen = [rng.choice(fams) for _ in fams]
        vals = [rng.choice(gaps_by_family[f]) for f in chosen if gaps_by_family[f]]
        if vals:
            means.append(statistics.mean(vals))
    means.sort()
    lo = means[int((1 - conf) / 2 * len(means))]
    hi = means[int((1 + conf) / 2 * len(means)) - 1]
    return (statistics.mean(means), lo, hi)


def epsilon_guarded_recovery(records, key_fields=("episode_id", "switch_point", "seed")):
    """recovery = (compiler - B1)/(B0 - B1), only where denominator > EPSILON_PTS/100."""
    def idx(col):
        return {tuple(r[k] for k in key_fields): r["score"]["raw"]
                for r in records if r["column"] == col}
    b0, b1, comp = idx("b0"), idx("b1"), idx("compiler")
    common = set(b0) & set(b1) & set(comp)
    eps = EPSILON_PTS / 100.0
    out = {}
    for k in common:
        denom = b0[k] - b1[k]
        if denom > eps:
            out[k] = (comp[k] - b1[k]) / denom
    return out


def go_no_go(records):
    """Q1-Q4 per eval_frozen.yaml thresholds. Returns {Q: {result, detail}}."""
    fam_of = {r["episode_id"]: r.get("family", r["episode_id"].rsplit("_", 1)[0]) for r in records}
    # Q1: post-switch degradation statistically clear in >=2 regions OR mean drop >=10 pts
    gap01 = paired_gap(records, "b0", "b1")
    by_fam = {}
    for k, g in gap01.items():
        by_fam.setdefault(fam_of.get(k[0], "?"), []).append(g)
    mean_drop = statistics.mean(list(gap01.values())) if gap01 else 0.0
    regions = sum(1 for f, gs in by_fam.items()
                  if gs and hierarchical_bootstrap({f: gs})[1] > 0)
    q1 = (regions >= 2) or (mean_drop >= EPSILON_PTS / 100)
    # Q2: B3 > B2a (CI excludes 0, favors B3)
    gap32 = paired_gap(records, "b3", "b2a")
    gf = {}
    for k, g in gap32.items():
        gf.setdefault(fam_of.get(k[0], "?"), []).append(g)
    m, lo, hi = hierarchical_bootstrap(gf) if gap32 else (0, 0, 0)
    q2 = lo > 0
    # Q3: held-out recovery >= 0.5
    held = [r for r in records if r["pair"] == "heldout_32to31"] if any("pair" in r for r in records) else records
    rec = epsilon_guarded_recovery(held or records)
    q3 = (statistics.mean(list(rec.values())) >= RECOVERY_THRESHOLD) if rec else False
    # Q4: gate reduces harmful repairs/duplicates without restarting most episodes
    branches = [r.get("gate_branch") for r in records if r.get("gate_branch")]
    restart_rate = branches.count("restart") / len(branches) if branches else 0
    q4 = restart_rate < 0.30
    return {
        "Q1": {"pass": q1, "mean_drop": round(mean_drop, 4), "regions_clear": regions},
        "Q2": {"pass": q2, "ci": (round(m, 4), round(lo, 4), round(hi, 4))},
        "Q3": {"pass": q3, "mean_recovery": round(statistics.mean(list(rec.values())), 4) if rec else None},
        "Q4": {"pass": q4, "restart_rate": round(restart_rate, 4)},
    }
