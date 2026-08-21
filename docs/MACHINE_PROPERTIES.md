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
