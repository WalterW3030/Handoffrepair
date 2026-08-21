# Execution Rules (always-on)

Binding on every execution step of the HandoffRepair pilot, in this sandbox and on the GPU machine. R1–R3 set by the user 2026-08-20; R4–R7 added 2026-08-20. Companion file: `Machine Properties.md`.

## R1 — Property awareness
- Always be aware of the recorded machine properties (driver, CUDA, disks, versions) and of every package/model/container version pinned in the repo.
- For anything not recorded or not sure: **check it first, or ask the user to check** — never guess. Open checks are listed in `Machine Properties.md` §3.

## R2 — Avoid sudo (amended 2026-08-20 per user)
- Never put sudo in scripts; always exhaust no-sudo alternatives first (user-space paths, env vars, rootless runtimes, group permissions).
- If sudo is genuinely necessary: present the exact minimal command to the user — **the user runs it themselves**.
- **Every necessary sudo use must be reported**: logged in `Machine Properties.md` change log with the command and why it was necessary. (Report #1: `sudo mkdir -p /ephemeral/hr`, 2026-08-20 — no user-writable dir existed on the only big disk.)

## R3 — Exactly 1 GPU
- All commands, scripts, and configs use exactly one GPU: `CUDA_VISIBLE_DEVICES=0` and/or `docker run --gpus '"device=0"'`.
- No tensor/pipeline parallelism, no multi-GPU flags (`--tensor-parallel-size` stays 1, vLLM default), no code that enumerates or splits across GPUs.
- Memory sizing must fit one GPU; if a model does not fit one GPU, that's a STOP, not a reason to span GPUs.

## R4 — Always a virtual environment
- All Python execution (setup, staging, dry-run, main run, analysis) happens inside an isolated environment, never against the system Python and never with `--user` installs.
- Accepted forms: the project venv (`<repo>/.venv`) **or a dedicated conda env** (user's machine uses conda) — one or the other, never both at once, and scripts must detect which is active.
- Scripts must either activate the env or call its interpreter explicitly; a missing env is a setup error, not a reason to fall back to system Python.
- The env's Python must be **3.10–3.12** (3.13 has no prebuilt wheels for some pinned deps → conda users: `conda create -n handoffrepair python=3.12`).

## R5 — Safe commands only
- Use only commands whose effect is confined to the experiment's own workspace (the repo dir, its venv, its evidence/log dirs, the HF cache on `/ephemeral` created by setup).
- **Never run commands that delete or overwrite files not created by this experiment** (no broad `rm -rf`, no cleanup of pre-existing directories, no touching other users' data, docker system prune, etc.).
- **Never run commands that affect state outside the environment** (system services, kernel settings, other mounts, shared caches, network config).
- If such a command appears genuinely necessary: **stop and ask the user for manual help**, presenting the exact command and its blast radius — never run it unilaterally.

## R6 — History before asking
- Before asking the user for any information, **first check the conversation history and the existing record files** (`AI manage AI/`, `docs/records/`, ledgers) — if it was already given, use it, never re-ask.
- Every important piece of information the user provides gets **recorded into the appropriate file promptly** (machine facts → `Machine Properties.md`, approvals → ledger, decisions → records), so it is never lost between sessions.

## R7 — Path errors: record, understand, update everywhere
On any path-related error (permission denied, no space, not found, stale location):
1. **Record it immediately** — the path, the error, and the root cause go into `Machine Properties.md` (change log) before fixing.
2. **Understand before fixing** — identify the root cause (permissions? stale variable? full disk? moved dir?), not just the symptom. Verify against the actual filesystem facts, never guess (R1).
3. **Update ALL related references** — every script, command, doc, and instruction that touches that path gets updated in the same pass, so no stale copy survives to fail again later. (Lesson: the `HF_HOME=/ephemeral/hf` failure happened because an old `env.sh` still carried the pre-move path while the scripts had moved on.)

## Standing pre-existing rules (unchanged)
- No GPU command without approval logged in the Staging Approval Ledger (staging approved 2026-08-18; main run still gated).
- Never move/overwrite tag `pilot-freeze-v1`. Never commit secrets. GitHub PAT is disposable — scrub after use. HF token read-only.
- No per-episode manual correction. Never fabricate data, evidence, or citations.
- self_flight self-check protocol stays always on (instruction declaration per task).
