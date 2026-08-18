# Pre-Flight Status Summary — HandoffRepair Pilot

**As of:** 2026-08-17 · Repo HEAD `075e7a8` · Tag `pilot-freeze-v1` archived (untouched) · No GPU run started

---

## ✅ Achieved (CPU-side, done by the agent)

| Class | What it is |
|---|---|
| Frozen configuration | All configs complete, no placeholders, single source of truth for sizing/budget |
| Frozen model & data pins | Model checkpoints + revisions, weight hash lock, episode set resolved, container image pinned by digest |
| Executable pipeline | All four pilot phases (calibrate / main / b6 / analyze) actually run, not stubs |
| Real dry-run evidence | All five columns executed through the real ToolSandbox world, pairing & world-identity assertions passed, scored by ToolSandbox's own evaluator |
| Test & verification suite | 18/18 tests pass, clean-environment one-command verification, discoverable test output |
| Unique run manifest + budget | 1,180 unique runs reconciled within the hard GPU-hour cap |
| Governance protocols | Append-only logging, idempotency, pre-flight gate (self_flight), bounded staging run sheet, no-manual-correction discipline |

## 📋 Planned (ready, CPU-side, will execute when unblocked)

| Class | What it is |
|---|---|
| Manifest execution machinery | Mock-mode full-manifest run (already works; formal full pass awaits GPU) |
| Analysis machinery | CIs / ε-recovery / Q1–Q4 verdicts — runs on any run log, ready for real data |
| Staging smoke | Run sheet written, bounded & auto-stopping — awaits approval + machine |

## 🖥️ Needs GPU (blocked until H100 80GB available)

| Class | What it is |
|---|---|
| Model launch evidence | Four models launched on H100, peak memory reported |
| Measured performance | Real per-pair runtime/token rates (replaces planning rates) |
| Parser gate execution | Gemma-4 tool-call probe set on the served model, fallback decision |
| Staging smoke execution | The bounded 6-GPU-hour staging run itself |
| Main pilot run | Full 1,180-run manifest + 150 B6 yardstick rollouts |
| Final release tag | New immutable RC tag (cut only after staging evidence exists) |

## 🤝 Work with human assistance (manual, no GPU needed)

| Class | What it is | Who |
|---|---|---|
| Advisor approval | Send staging run sheet, obtain written go-ahead for staging only | User |
| Weight pre-staging | Download 4 models at pinned revisions on any CPU machine, verify hashes, transfer to rental | User |
| Digest spot-check | Pull the pinned container on any Docker host, confirm match | User |
| Credential hygiene | Keep GitHub PAT until final tag push, then revoke; HF token read-only | User |
| Rental selection | H100 SXM5 80GB, ≥16 vCPU, ≥128GB RAM, ≥500GB NVMe, Docker + network access | User |
| Recurring slots | Day-2 extraction audit (~2h) + daily status trigger | User (+ agent reminder) |
