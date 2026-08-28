# Machine Properties (recorded)
Source: user-provided command outputs, 2026-08-20. Per Execution Rule R1: anything not here is unknown — check or ask, never guess.

## 1. Recorded facts

### GPU driver / CUDA
| Property | Value |
|---|---|
| NVIDIA-SMI | 570.195.03 |
| Driver version | 570.195.03 |
| CUDA version (driver-supported max) | 12.8 |

### Storage (`df -h`)
| Filesystem | Size | Used | Avail | Use% | Mounted on |
|---|---|---|---|---|---|
| tmpfs | 142G | 2.4M | 142G | 1% | /run |
| /dev/vda1 | 96G | 94G | **2.2G** | **98%** | **/** (root — critically full; filled further by failed docker pull's partial layers) |
| tmpfs | 709G | 250M | 709G | 1% | /dev/shm |
| tmpfs | 5.0M | 0 | 5.0M | 0% | /run/lock |
| tmpfs | 709G | 0 | 709G | 0% | /run/qemu |
| /dev/vda16 | 881M | 183M | 637M | 23% | /boot |
| /dev/vda15 | 105M | 6.2M | 99M | 6% | /boot/efi |
| /dev/vdb | 6.3T | 5.7T | **317G** | 95% | **/ephemeral** — root:root 755 top level; other subdirs belong to other users (not listed per privacy). **User created `/ephemeral/hr`** (sudo, 2026-08-20, reported) → canonical base dir: **`PILOT_DATA=/ephemeral/hr/pilot`** |
| tmpfs | 142G | 400K | 142G | 1% | /run/user/1000 |

### GPU (from approval records — Day 0 Record 4 §remaining, Record 9 H1, Staging Approval Ledger)
| Property | Value |
|---|---|
| Machine spec (approved) | **1× H100 SXM5 80GB**, ≥16 vCPU, ≥128GB RAM, ≥500GB NVMe |
| Hostname | `h800-8-1` (misleading name — GPUs are H100, see below) |
| GPU (CONFIRMED 2026-08-20, user nvidia-smi) | **8× NVIDIA H100 PCIe, 81559 MiB each** — H100 confirmed (not H800). R3: we use exactly **1** (device 0) regardless. sm_90, FP8 OK, matches container arch |
| User account | `ubuntu` uid=1000, groups: adm, **sudo**, dip, lxd, libvirt, **docker** — note: user HAS sudo capability; R2 (no sudo) is a project policy the user set, kept as-is |
| vLLM arch target | sm_90 (H100) — matches pinned container's arch list |

### Runtime environment (user-reported 2026-08-20, check answers A2–A5)
| Property | Value |
|---|---|
| Conda env python | **3.12** ✅ (within required 3.10–3.12) |
| Docker | Engine Community **29.1.3** (API 1.52, containerd 2.2.1, runc 1.3.4) — client+server respond **as user, no sudo** ✅ (docker group OK) |
| Docker storage | ⚠️ **CORRECTED 2026-08-20**: image layers actually write to **`/var/lib/containerd`** (containerd snapshotter), which is on **`/` (11 G free)** → ~20 GB vLLM pull failed "no space left on device". The earlier `>40G on /var/lib/docker` was misleading (wrong path). **Fix: rootless docker with data on `/ephemeral`** (no sudo) — commands in `staging_collect.sh` §0b stop message |
| Machine network | `huggingface.co` → **HTTP/2 200** ✅; `registry-1.docker.io` reachable ✅ (weight/image pulls possible machine-side) |

### Consequences (derived, binding for all planning)
- **Everything large lives on `/ephemeral`**: HF cache (`HF_HOME=$PILOT_DATA/hf`, canonical `/ephemeral/hr/pilot/hf`), repo clone, docker data if movable, all logs/evidence. Root `/` has 11 G free — the ~230 GB of weights + ~20 GB container image cannot touch `/`.
- **429 G avail vs plan**: weights ≈230 G + vLLM image ≈20 G + logs/evidence ≈10 G ≈ 260 G → fits with ~170 G headroom. Tight but OK. `/ephemeral` is likely wiped on machine release (name suggests it) → evidence must be uploaded/exported after each phase.
- Large RAM (≥700 G by tmpfs sizing) — host-side processing unconstrained.

## 2. Version pins this machine must satisfy (from repo)
| Component | Pin |
|---|---|
| ToolSandbox | commit 165848b9a78cead7ca7fe7c89c688b58e6501219 from **`apple/ToolSandbox`** (upstream moved from `facebookresearch/ToolSandbox`, which now 404s; pinned commit verified present in apple repo 2026-08-20) |
| vLLM image | vllm/vllm-openai@sha256:0a51ea5b…bfd967 (v0.27.1, CUDA 13.0.2 user-space, sm_90) |
| Models | Qwen3-32B 9216db57 · Qwen3-8B b968826d · RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic f50dbad2 · google/gemma-4-31B-it 842da379 |
| Weights | 39-file SHA-256 lock (`configs/weight_sha256.lock`) |
| Host python deps | per `scripts/setup_machine.sh` (polars==0.20.31, pydantic==2.7.4, openai==1.17.0, …) |


### Machine filesystem / access (user-reported 2026-08-20)
| Property | Value |
|---|---|
| Working path | **`/ephemeral/hr/Handoffrepair`** (repo MOVED here 2026-08-20 — root disk `/` only 2.2 G free; old path `/home/ubuntu/HandoffRepair/Handoffrepair` is retired) |
| SSH deploy key | `~/.ssh/id_ed25519_ww3030` (+ `.pub`) — added to GitHub repo deploy keys |
| GitHub repo (correct URL) | **`git@github.com:WalterW3030/Handoffrepair.git`** (SSH, deploy key) · `https://github.com/WalterW3030/Handoffrepair.git` (HTTPS). Owner = user account `WalterW3030`, repo name `Handoffrepair` — any URL with owner `handoffrepair` or name `handoffrepair-pilot` is WRONG (the cause of all earlier push/clone failures) |
| Repo directory name on machine | `Handoffrepair` (user's original clone; canonical name — all scripts are dirname-agnostic) |

**Clone error diagnosis (2026-08-20):** `Repository not found` with a *working* key = wrong repo **name** in the URL, not an auth failure (auth failure says "Permission denied"). My earlier instructions used `handoffrepair-pilot`; the actual repo is `Handoffrepair`. Correct clone command:
```bash
git clone -c core.sshCommand="ssh -i ~/.ssh/id_ed25519_ww3030" git@github.com:handoffrepair/Handoffrepair.git
```
Local sandbox copy renamed to `Handoffrepair` to match (commit pending); scripts use `cd "$(dirname "$0")/.."` so they work under any directory name.

## 3. Open checks — remaining
1. ~~gemma-4 license acceptance~~ ✅ accepted by user (2026-08-20, confirmed in chat).
2. **RAPID_API_KEY**: received from user 2026-08-20 — **handled as secret**: never written to repo/docs, stored as env var on the machine only (`export RAPID_API_KEY=...` in `~/.bashrc`); validity verified by the probe in `setup_machine.sh` §5b (records PASS/FAIL only, never the value).
3. **Driver vs container CUDA**: pinned vLLM image is CUDA 13.0.2 user-space; driver 570.195.03 supports max CUDA 12.8. CUDA 13 normally wants driver ≥580; on datacenter GPUs the container's `cuda-compat` may bridge this, but it is **not guaranteed**. Definitive test (staging_collect.sh runs it first, auto-stops): `docker run --rm --gpus '"device=0"' <pinned vllm image> nvidia-smi`. **Last technical unknown.**
4. ~~GitHub push~~ ✅ **RESOLVED 2026-08-20**: root cause was the wrong URL — owner `WalterW3030` (user account), repo `Handoffrepair`. PAT was valid all along; API confirmed user + repo, push `cdaa586..b101939` succeeded and verified via API (commit sha + 5 file checks, all 200). Remote scrubbed of PAT. Clone URL: `git@github.com:WalterW3030/Handoffrepair.git`

## 3b. Sudo use log (per R2 reporting duty)
| # | Date | Command | Why necessary | Executed by |
|---|---|---|---|---|
| 1 | 2026-08-20 | `sudo mkdir -p /ephemeral/hr` | No user-writable dir on the only big disk; no no-sudo alternative | user |
| 2 | 2026-08-20 | `sudo chown ubuntu:ubuntu /ephemeral/hr` | Make /ephemeral/hr writable by user | user |
| 3 | 2026-08-20 | `sudo mkdir/tee /etc/docker/daemon.json` + `sudo systemctl restart docker` | Relocate system-docker storage to /ephemeral/hr/docker-data (root / too small) — **INSUFFICIENT on Docker 29**, see #5 | user |
| 5 | 2026-08-21 | `daemon.json`: add `"features":{"containerd-snapshotter":false}` + restart docker | **Docker 29 defaults to the containerd image store** → image layers go to `/var/lib/containerd` (on `/`), which `data-root` does NOT move. Disabling the snapshotter reverts images to overlay2 under `data-root` (/ephemeral). Verified via Docker docs. | user |
| 4 | (only if rootless chosen) | `sudo apt install uidmap` | Rootless docker needs setuid `newuidmap`/`newgidmap` (confirmed missing 2026-08-21); no no-sudo alternative | user |

## 4. Change log
- 2026-08-21 — **staging evidence read** (user log): python 3.12.0 ✓, RAM 1.4TB ✓, DockerRootDir=/ephemeral/hr/docker-data 202G ✓, digest MATCH ✓. CUDA probe FAILED but NOT a CUDA issue: image entrypoint is `vllm serve`, so `docker run IMAGE nvidia-smi` made vLLM treat `nvidia-smi` as a model → 401 from HF. Fixed: probe now uses `--entrypoint nvidia-smi`. HF token never reached a real model yet.
- 2026-08-21 — HF_TOKEN set but INVALID ('Invalid user token'). HF_TOKEN env takes precedence over `hf auth login`. Fix: re-export a fresh valid token; verify with `hf auth whoami` (never echo/paste the token itself).
- 2026-08-21 — staging progress: disk fix WORKED (containerd-snapshotter disabled, image pulled to /ephemeral, container launched, CUDA-compat probe PASSED). New failure: vLLM HF auth error — HF_TOKEN unset in shell OR gemma-4 gated-license not accepted. Fixed staging_collect.sh: (a) HF_TOKEN pre-check before launches, (b) health-loop now distinguishes HF-auth failure from a real crash instead of misreporting as CUDA mismatch.
- 2026-08-21 — **Docker 29 storage trap**: containerd image store is default → image layers in /var/lib/containerd (NOT moved by data-root). Fix = features.containerd-snapshotter=false in daemon.json. This was the real cause of the repeated 'no space left on /var/lib/containerd' pull failures.
- 2026-08-21 — rootless docker root cause: `newuidmap`/`newgidmap` missing (uidmap pkg); subuid/subgid/userns/XDG_RUNTIME_DIR all OK. System-docker path is primary (works, storage on /ephemeral).
- 2026-08-20 — docker mode: user has docker group → SYSTEM docker is the default (no sudo for docker cmds); storage relocated to /ephemeral/hr/docker-data via one reported sudo edit. env.sh/staging now support DOCKER_MODE=system|rootless (default system). Rootless remains the no-sudo fallback.
- 2026-08-20 — rootless docker daemon must be started persistently (setsid, survives shell exit) and DOCKER_HOST exported in every shell; added daemon-reachable pre-flight to staging_collect.sh + DOCKER_HOST to env.sh. (Error: docker.sock no such file = daemon not running.)
- 2026-08-20 — HF_HOME stale-override bug: old env.sh/shell had HF_HOME=/ephemeral/hf (root-owned, from pre-PILOT_DATA runs) → PermissionError on weight download. Scripts now force HF_HOME under PILOT_DATA with a warning when ignoring a stale value.
- 2026-08-20 — repo moved to /ephemeral/hr/Handoffrepair (user-executed mv); huggingface-cli deprecated → scripts use `hf` only.
- 2026-08-20 — initial record from user paste; rules R1–R3 established.
- 2026-08-20 — GPU spec recovered from approval records (H100 SXM5 80GB; rule R6 created from this miss); A2–A5 check answers recorded: conda py3.12, Docker CE 29.1.3 no-sudo OK, /var/lib/docker >40G free, HF+Docker Hub reachable.
- 2026-08-20 — setup_machine.sh step-order bug fixed: import smoke test ran before env.sh/PYTHONPATH was set → ModuleNotFoundError tool_sandbox; env.sh creation moved before the smoke test.
- 2026-08-20 — **sudo use report #1**: `sudo mkdir -p /ephemeral/hr` (user-executed, necessary: no user-writable dir on /ephemeral, no alternative). GPUs confirmed 8×H100 PCIe 81.5GB.
- 2026-08-20 — hostname h800-8-1 recorded (H800? pending nvidia-smi confirmation); user groups recorded (sudo present, policy unchanged).
- 2026-08-20 — /ephemeral is root-owned at top level; user ubuntu cannot create /ephemeral/ubuntu. Rule: never write to unpermitted paths (R5); use a user-writable base dir on /ephemeral.
- 2026-08-20 — disk state updated from user df: / 2.2G free (98%), /ephemeral 317G free. Root filled by failed pull's partial containerd layers. vLLM images must go to /ephemeral via rootless docker.
- 2026-08-20 — docker storage root cause: layers go to /var/lib/containerd on / (11G), not /var/lib/docker; rootless-docker-on-/ephemeral is the no-sudo fix; staging_collect.sh now pre-flights the real path.
- 2026-08-20 — ToolSandbox upstream URL fixed: facebookresearch/ToolSandbox 404s (moved); apple/ToolSandbox contains the pinned commit. setup_machine.sh corrected.
- 2026-08-20 — push resolved: correct URL github.com/WalterW3030/Handoffrepair; all 9 commits now on GitHub, verified via API.
- 2026-08-20 — C.1: machine path /home/ubuntu/HandoffRepair, deploy key id_ed25519_ww3030, repo name corrected to Handoffrepair (clone error diagnosed: wrong repo name, not auth).
- 2026-08-20 — B6–B8: SSH deploy key added (machine-side sync); gemma-4 license accepted; RAPID_API_KEY received (secret: env var only, probe logs pass/fail only). GitHub egress from sandbox blocked → push pending.
- 2026-08-22 — staging_collect.sh: stale-container name conflict. Root cause: since --rm was dropped (b561b8f), a STOP on dead server exits before the end-of-loop cleanup, leaving dead container `staging_<key>` holding the name; next run's `docker run --name` conflicts. Fix: `docker rm -f staging_$key` before each launch (idempotent). Also removed stray duplicate `[ "$mem" -gt "$peak" ]` line (ran before mem assignment). Stale 65-byte evidence/serve_qwen3-32b.log ("No such container", from the --rm era) removed from repo — no diagnostic value; the real crash log is still outstanding.
- 2026-08-22 — BROKE the qwen-log loop (3 rounds, never got a real log). Root causes were NOT Qwen/OOM-specific: (a) script had NO --ipc=host, which vLLM's OpenAI image requires (PyTorch shm IPC) — a startup killer on ANY model; (b) no pre-launch container cleanup → "name already in use" on every re-run; (c) log capture only ran inside the poll loop, so the real crash was never captured. Fixes: add --ipc=host, pre-clean before launch, capture_diag() records exit_code/oom_killed/error always, gpu-memory-utilization 0.95→0.90. Removed stale evidence/serve_qwen3-32b.log (65B "No such container", no diagnostic value).
- 2026-08-22 — **LOOP ROOT-CAUSE ANALYSIS (self-critique, R9 origin).** 4+ rounds, never captured the real error. The mechanism of WHY we kept getting "No such container" instead of the traceback:
  (1) MY LOGIC ERROR — capture ran `docker logs` AFTER detecting death via `docker ps`; on a fast crash the container can be gone/renamed before the capture, so `docker logs` printed "No such container" (an ERROR from the docker CLI) which the script then wrote INTO serve_<key>.log as if it were the crash output. We were logging the failure of our own probe, not the crash.
  (2) ANCHORING — I picked OOM early (biggest model + tight GPU budget) and kept patching the *capture plumbing* instead of questioning the theory. Never verified the log file had real content before reasoning from it.
  (3) EVIDENCE — user's diag finally showed `exit_code=1, oom_killed=false`: NOT OOM, NOT shm-kill(137), NOT segfault(139). exit 1 = vLLM raised a Python exception and self-exited = config/arg/model-resolution error. OOM theory formally dead.
  (4) FIX PRINCIPLE — capture stdout/stderr DIRECTLY from the run (redirect docker run output to a file, or use --rm and read the pipe), never post-hoc `docker logs` on a possibly-dead container. Record R9 added to EXECUTION_RULES.
- 2026-08-22 — **Root cause identified (evidence-backed, R9/R10): all 6 vLLM launchers used `--model <name>`, but the image entrypoint is `vllm serve`, which per vLLM source raises ValueError("...provide the model as a positional argument instead of via the --model option") → exit 1.** This matches every observed fact: exit_code=1, oom_killed=false, fast death, all four models equally affected (NOT Qwen-specific, NOT OOM). Fix: model now passed positionally in staging_collect.sh, quick_probe.sh, serve_*.sh (4). Also: user's docker ps revealed my probe command's doubled "vllm serve serve" (my error, caught). The stuck "Created" qp32 container came from the broken-tee pipe at launch. Caveat (recorded per R10): in vLLM ≥0.14 the --model misuse degrades to a WARNING not a hard error — pinned image behavior to be confirmed by the probe run.
- 2026-08-28 — **TRUE root cause captured (real traceback, user upload)**: `ValueError: Free memory on device cuda:0 (45.89/79.19 GiB) on startup is less than desired GPU memory utilization (0.9, 71.27 GiB)`. GPU 0 held ~33 GiB by ANOTHER process (shared 8-GPU machine) — never "model too big for card". The positional-model fix worked (engine reached memory init; resolved Qwen3ForCausalLM, NCCL up). Also observed: "unauthenticated requests to HF Hub" warning → HF_TOKEN was NOT set in that shell (env.shsh typo run); Qwen is public so fine, but gated gemma-4 requires it. Fixes applied to ALL launchers: freest-GPU auto-selection (GPU_ID env override), 73 GiB free-memory pre-flight, drop `-e CUDA_VISIBLE_DEVICES=0` (redundant/confusing with --gpus device=N), memory sampling points at selected GPU, serving util 0.95→0.90 to match staging. R3 amended in practice: exactly one GPU, but NOT hardcoded to device 0.
- 2026-08-28 — GPU availability (user-reported): **GPUs 5, 6, 7 are free**. R3 amended: at most 1 GPU AND always check availability via nvidia-smi before every GPU run — occupancy changes on this shared machine, so re-check each time rather than trusting this snapshot.
