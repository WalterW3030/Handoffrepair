# Execution Rules (always-on)

Binding on every execution step of the HandoffRepair pilot, in this sandbox and on the GPU machine. Set by the user 2026-08-20. Companion file: `Machine Properties.md`.

## R1 — Property awareness
- Always be aware of the recorded machine properties (driver, CUDA, disks, versions) and of every package/model/container version pinned in the repo.
- For anything not recorded or not sure: **check it first, or ask the user to check** — never guess. Open checks are listed in `Machine Properties.md` §3.

## R2 — No sudo
- Never use sudo in any script or command, and never ask the user to run sudo.
- If something seems to need sudo (e.g. Docker daemon config), first exhaust alternatives: user-space paths (`$HOME`, `/ephemeral`), environment variables (`HF_HOME`, `XDG_DATA_HOME`), rootless runtimes (rootless podman/docker), per-user permissions (docker group — the user checks, not sudo-installs).
- Only if all alternatives are exhausted, report the blocker and the exact minimal privileged action to the user as a decision — never as a step to silently run.

## R3 — Exactly 1 GPU
- All commands, scripts, and configs use exactly one GPU: `CUDA_VISIBLE_DEVICES=0` and/or `docker run --gpus '"device=0"'`.
- No tensor/pipeline parallelism, no multi-GPU flags (`--tensor-parallel-size` stays 1, vLLM default), no code that enumerates or splits across GPUs.
- Memory sizing must fit one GPU; if a model does not fit one GPU, that's a STOP, not a reason to span GPUs.

## Standing pre-existing rules (unchanged)
- No GPU command without approval logged in the Staging Approval Ledger (staging approved 2026-08-18; main run still gated).
- Never move/overwrite tag `pilot-freeze-v1`. Never commit secrets. GitHub PAT is disposable — scrub after use. HF token read-only.
- No per-episode manual correction. Never fabricate data, evidence, or citations.
- self_flight self-check protocol stays always on (instruction declaration per task).
