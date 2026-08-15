# Clean-environment verification (CPU; no GPU needed)

From a fresh clone, one command verifies the entire CPU-verifiable harness:

```bash
git clone https://github.com/WalterW3030/Handoffrepair.git && cd Handoffrepair
python -m venv .venv && . .venv/bin/activate        # or: python3 -m pip install -r requirements-lock.txt
pip install -r requirements-lock.txt
python -m pytest tests/ -q                           # expect: 13 passed
```

`tests/test_pilot.py` covers: hand-computed scorer cases, a successful end-to-end episode,
cross-column prefix equality (B1/B2a/B3/compiler), duplicate side-effect suppression,
transport-retry op-ID reuse, gate restart/replay branches, manifest count/accounting
assertions, unique-run log integrity, timeout bound, and parser-failure last-resort.

## Dependency lock / container

- Python harness: `requirements-lock.txt` (pinned).
- GPU serving stack: pinned by **container image digest** at Day 0 staging (recorded into
  `configs/models.yaml: serving.vllm_version`), because the digest is only resolvable once the
  exact vLLM/PyTorch/CUDA/driver combination is chosen on the H100. This is the one intentionally
  staging-derived value; everything CPU-resolvable is locked here.

## What this does NOT verify (GPU-bound, by design)

Model launch, peak memory, measured tokens/second, real ToolSandbox episodes, and the B6
yardstick — these require the H100 and are produced by the bounded staging-smoke run sheet
(`staging_smoke_runsheet.md`), which is executed only after advisor approval.
