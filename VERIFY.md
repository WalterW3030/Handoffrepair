# Clean-environment verification (CPU; no GPU needed)

From a fresh clone, one command verifies the entire CPU-verifiable harness:

```bash
git clone https://github.com/WalterW3030/Handoffrepair.git && cd Handoffrepair
python -m venv .venv && . .venv/bin/activate        # or: python3 -m pip install -r requirements-lock.txt
pip install -r requirements-lock.txt
python -m pytest tests/ -q                           # expect: 13 passed (18 with ToolSandbox present)
```

`tests/test_pilot.py` covers: hand-computed scorer cases, a successful end-to-end episode,
cross-column prefix equality (B1/B2a/B3/compiler), duplicate side-effect suppression,
transport-retry op-ID reuse, gate restart/replay branches, manifest count/accounting
assertions, unique-run log integrity, timeout bound, and parser-failure last-resort.

## Real ToolSandbox dry-run (CPU; advisor final-submission item)

With the pinned ToolSandbox checkout (commit `165848b9a78cead7ca7fe7c89c688b58e6501219`)
and its pinned deps (polars==0.20.31, pydantic==2.7.4, StrEnum==0.4.15, rapidfuzz==3.9.3,
dill==0.3.8, langchain==0.1.3, openai==1.17.0, anthropic==0.26.1):

```bash
export TOOLSANDBOX_REPO=/path/to/ToolSandbox
python src/toolsandbox/dry_run.py --repo $TOOLSANDBOX_REPO \
    --scenario add_reminder_content_and_date_and_time --out logs/toolsandbox_dry_run.json
# expect: all five columns similarity=1.000, A1 prefix identity PASS, A2 world identity PASS
python -m pytest tests/test_toolsandbox_dryrun.py -q   # expect: 5 passed

# full pipeline phases, all executable end-to-end in mock mode:
python src/run_pilot.py --phase calibrate              # timed runs -> logs/measured_rates.json
python src/run_pilot.py --phase main                   # manifest + cell-coverage smoke (33 runs)
python src/run_pilot.py --phase b6                     # yardstick accounting path
python src/run_pilot.py --phase analyze                # CIs + Q1-Q4 from the append-only log
```

Dry-run evidence (Day 0, this repo): `logs/toolsandbox_dry_run.json` — B0/B1/B2a/B3/compiler
all score 1.000 via ToolSandbox's own milestone/minefield evaluator; prefix anchor identical
across handoff columns; final REMINDER world state byte-identical across all five columns;
`handoff_info_sufficient` discriminates B1 (true) vs B2a/B3/compiler (false) at S1.

## Dependency lock / container

- Python harness: `requirements-lock.txt` (pinned).
- ToolSandbox deps: pinned versions listed above (recorded in `src/toolsandbox/INTEGRATION.md`).
- GPU serving stack: pinned by **container image digest** in `configs/models.yaml`
  (`serving.container_image` = `vllm/vllm-openai@sha256:0a51ea5b…`, resolved via registry
  metadata 2026-08-17; CUDA 13.0.2, arch list includes sm_90/H100). Staging re-verifies the
  digest on the H100 with `docker pull` — no staging-derived value remains.

## What this does NOT verify (GPU-bound, by design)

Model launch, peak memory, measured tokens/second, GPU-mode episodes, and the full B6
yardstick — these require the H100 and are produced by the bounded staging-smoke run sheet
(`staging_smoke_runsheet.md`), which is executed only after advisor approval.
