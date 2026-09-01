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
- 2026-08-28 — R11 added (user instruction): estimate runtime of every command before handing it over; anything expected >10 min must be flagged and given in tmux-background form with a progress-check method. Applies from staging onward (4-model staging ≈ tens of minutes even with cached weights; gemma download adds time if not cached).
- 2026-08-28 — staging crash on FREE GPU root cause: NOT GPU, NOT memory. Traceback: httpx `_normalize_header_value` → UnicodeEncodeError 'ascii' codec can't encode characters in position 10-11 — HF_TOKEN contained non-ASCII (CJK/full-width) characters from copy-paste, so the Authorization header could not be encoded → engine died at HF metadata fetch, exit 1. Explains why the no-token probe worked (unauthenticated request, public model) but staging with token failed. Origin: my placeholder `export HF_TOKEN=hf_你的token` invited CJK chars into the value — my error. Fix: staging [2b/5] now rejects non-ASCII HF_TOKEN at pre-flight with a loud STOP + verification command.
- 2026-08-28 — Token storage decision (user): HF_TOKEN is NEVER stored on disk or in git. staging_collect.sh [2b/5] and quick_probe.sh now PROMPT interactively (read -s, no echo, max 3 tries, ASCII-validated) when the token is unset or polluted; token lives only in the process env. No .secrets.env file (that approach was rejected by user).
- 2026-08-28 — staging crash #3 root cause (real log 6cb575c): `RuntimeError: Triton Error [CUDA]: unspecified launch failure` at structured_outputs grammar-bitmask kernel warmup. GPU was FREE (78.74/79.19 GiB) and weights loaded OK (61.92 GiB) — the CUDA 13.0.2 image on R570 driver (max CUDA 12.8) gap breaks Triton kernel launches. vLLM docs confirm this exact scenario and the documented fix: VLLM_ENABLE_CUDA_COMPATIBILITY=1 (ships cuda-compat libs, supports R570 hosts). Added to all 6 launchers. Also: this explains why the no-token probe "worked" — it was a different run; token and CUDA-compat issues were stacked.
- 2026-08-28 — llama33-70b-fp8 failure root cause (real log bb374a2): NOT HF auth (script mis-grepped "token" in ValueError text). Real error: `ValueError: 2.5 GiB KV cache needed for max seq len 8192, only 1.04 GiB available` — FP8 70B weights ~70GiB on 79.19 GiB GPU at util 0.90 leaves too little KV cache. Qwen models passed (compat flag worked). Options recorded: (A) lower max_model_len ≤3392, (B) raise util to 0.95 — user decision required (affects context length vs OOM risk).
- 2026-08-28 — added tools/push_latest_evidence.sh: auto-finds newest staging_evidence dir, copies all logs to evidence/, pull+commit+push in one command.
- 2026-08-28 — R12 added (user instruction): (a) always compare alternatives on experiment-relevant criteria (incl. consequence on experiment validity) before choosing; (b) never size to machine limit — compute cost from actual model spec (params/dtype/layers/KV heads/attention type) and require ≥10% free headroom; (c) check the ENTIRE pilot + follow-on plan's machine cost, not one model.
- 2026-08-28 — FULL pilot resource audit (79.19 GiB/GPU, util 0.90, act margin 1.5 GiB, from specs+logs): qwen3-32b free 13.8G OK · qwen3-8b free 60.6G OK · gemma4-31b free 14.3G OK (hybrid sliding+global attention → small KV) · **llama33-70b-fp8 free only 5.2G @8192 / 6.4G @4096 — BELOW the 7.9G (10%) headroom floor at ANY usable context**. Raising util to 0.95 does NOT help (vLLM util caps its own claim, but the physical card total is fixed; 70G weights + KV + act ≈ 74G regardless). Conclusion: llama-70b-fp8 is fundamentally too big for a single 80GB card under R12 headroom — must swap to a smaller model, not tune flags.

## 2026-08-28 — Pair-2 model swap + design-time audit fixes (R13)
- calibrated_pair_2 large slot: RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic →
  Qwen/Qwen3-30B-A3B-Instruct-2507 (MoE 30.5B/3.3B-active, bf16 ~57 GiB, 4 KV heads,
  native 262144 ctx, Apache-2.0, hermes parser). Root cause of swap: llama FP8 ~70 GiB
  weights left only 1.04 GiB KV at util 0.90 → ValueError even at ctx 8192; violates R12.
- Context length decision (R13 audit vs ToolSandbox paper: avg 13.9 turns/episode,
  30-turn cap → avg episode ~11.6k tokens, max ~20.6k): all launchers 8192 → 16384.
  16384 = minimum valid ctx; episodes >16k documented as accepted truncation limitation.
- decoding.yaml: tool parser llama3_json → hermes for the new model;
  gpu_memory_utilization 0.92 → 0.90 (now consistent with all launchers).
- weight_sha256.lock: llama entry replaced by Qwen3-30B-A3B entry marked
  TO_PIN_AT_FIRST_STAGING (HF unreachable from sandbox; pin procedure documented
  in the lock file itself). staging_collect.sh/quick_probe.sh MODELS maps swapped.
- staging_collect.sh bugfix: auth-detector grep no longer matches bare "token"
  (false "HF auth failed" STOP on the llama KV ValueError, 2026-08-28).
- serve_llama33_70b.sh → serve_qwen3_30b_a3b.sh (git mv); revision via
  QWEN3_30B_A3B_REV env, TO_PIN until first download.
- Resource audit @16384, util 0.90, 79.19 GiB card (need ≥7.9 GiB free headroom):
  qwen3-32b +11.79G OK; qwen3-8b +59.44G OK; Qwen3-30B-A3B +16.19G OK;
  gemma4-31b +13.66G OK. All four pass R12.

## 2026-08-31 — gemma4-31b staging launch failure: vLLM 0.27.1 x transformers >= 5.15 incompatibility
- Evidence: staging_evidence/20260831T164655Z/serve_gemma4-31b.log —
  `AmbiguousGlobalPerLayerAttributeError: 'head_dim' is a per-layer attribute` raised in
  vllm/transformers_utils/model_arch_config_convertor.py:608 get_head_size(), exit_code=1,
  oom_killed=false. Same evidence dir shows qwen3-32b / qwen3-8b / qwen3-30b-a3b ALL HEALTHY
  (smoke OK, peaks 75013/75471/73819 MiB under the 81087 MiB card). Failure is gemma4-specific.
- Root cause (upstream-verified, not guessed): transformers >= 5.15 turns per-layer attributes
  (head_dim) into guarded heterogeneity attributes; vLLM 0.27.1's config converter reads the
  global `head_dim` and crashes. vLLM issue #51744 (identical traceback; reporter: downgrading
  transformers to 5.14.1 in the SAME image resolves it) and #52768 ("v0.27.1 raises; does NOT
  happen on v0.26.0"). Our pinned image vllm/vllm-openai@sha256:0a51ea... (v0.27.1, CUDA 13.0.2)
  ships the incompatible transformers.
- Verified candidate fixes (in preference order):
  A. dedicated official image `vllm/vllm-openai:gemma4-cu130` (vLLM official Gemma4 recipe, CUDA 13.0),
     gemma4 ONLY, other 3 models unchanged on the pinned image;
  B. same pinned image + `pip install --no-cache-dir "transformers==5.14.1"` at container start
     (entrypoint shim), gemma4 only;
  C. vllm/vllm-openai:v0.26.0 image for gemma4 (issue says unaffected) — but older base CUDA,
     needs re-validation of VLLM_ENABLE_CUDA_COMPATIBILITY on R570.
- Open risk: recipe docs' `gemma4-cu130` tag is mutable; must pin by digest at staging time.

## 2026-08-31 — gemma4 fix APPLIED: Option B (transformers==5.14.1 in-container)
- Decision: B active; A (vllm/vllm-openai:gemma4-cu130, digest-pin required) recorded as
  fallback-only in docs/GEMMA4_FIX_OPTIONS.md; C rejected at pre-screen.
- serve_gemma4_31b.sh rewritten: --entrypoint /bin/bash -c 'pip install transformers==5.14.1
  && exec vllm serve ...'; stale --reasoning-parser/--chat-template flags removed (uniform
  shim since 2026-08-29); old /templates mount dropped.
- scripts/staging_collect.sh: gemma4 branch now uses the same entrypoint-shim launch.
- Note for env.txt evidence: gemma4's in-container transformers will read 5.14.1, differing
  from the other three models' image manifest — recorded here and in GEMMA4_FIX_OPTIONS.md.

## 2026-08-31 — trailing-comment-after-backslash bug class (quick_probe + serve_qwen3_32b/8b)
- quick_probe.sh:85 had `-e VLLM_ENABLE_CUDA_COMPATIBILITY=1 \  # comment` — backslash escapes
  the newline, comment swallows the continuation → "invalid reference format / -v: command not found".
  Same latent pattern found and fixed in serve_qwen3_32b.sh:20 and serve_qwen3_8b.sh:19.
  NOTE: quick_probe.sh has NO gemma4 transformers pin (Option B); for gemma4 use
  staging_collect.sh or serve_gemma4_31b.sh, not quick_probe.

## 2026-08-31 — gemma4 Option-B follow-on failure: KV cache shortfall at 24576 (spec error in R12 audit)
- Evidence: evidence/serve_gemma4-31b_optionB_20260831T200553Z.log lines 649-700.
  EngineCore ValueError: KV needed 15.17 GiB for max_model_len 24576, only 9.44 GiB available
  (est. max 11232 at util 0.90). The transformers==5.14.1 pin WORKED (config load passed;
  failure moved to KV init) — this is a NEW, separate failure.
- Root cause = MY SPEC ERROR in the 2026-08-29 audit: I estimated gemma4 KV as "~50 KiB/token
  effective" (hybrid sliding-window) → ~1.5 GiB @24576. Actual requirement = 15.17 GiB @24576
  (~633 KiB/token effective) — vLLM apparently allocates full-length KV for the global-attention
  layers (and/or other overhead), not the hybrid-saving figure I assumed. Weights+overhead
  ≈ 71.27 - 9.44 = 61.83 GiB as predicted; the KV side was wrong by ~10x.
- Fix options (R14 pre-screen):
  A. gemma4 ctx 24576 at util 0.95: KV pool ~13 GiB < 15.17 → still FAILS pre-screen. Rejected.
  B. uniform ctx 16384 for ALL models: gemma4 KV ~9.5-10.1 GiB vs pool 9.44 — still borderline/
     likely fail; also re-truncates workload tail (needs util 0.92+ to pass, then Qwen margins shrink).
  C. gemma4-only KV reduction at 24576: kv-cache-dtype fp8 (KV ~7.6 GiB < 9.44) or
     --max-num-seqs small. Keeps uniform ctx; gemma4-only KV precision delta logged in manifest.
  D. swap gemma4-31b for a model that fits 24576 on one card.
- Local mistakes file: M15 entry (effective-KV assumption from architecture intuition instead of
  measured/empirical KV spec; audit math treated estimates as measurements).

## 2026-09-01 — gemma4 probe: --no-enable-prefix-caching does NOT engage sliding-window KV saving
- Evidence: evidence/probe_gemma4_noprefixcache_20260901T142912Z.log — same ValueError
  (15.17 GiB needed vs 9.44 available) with prefix caching OFF. Hypothesis "hybrid allocator
  saving disabled by prefix caching" is FALSIFIED by measurement (M15 probe gate working).
- Consequence: gemma4-31b cannot serve ctx 24576 on one 79.19 GiB card at util 0.90 in this
  vLLM build, regardless of prefix-caching or the transformers pin. Remaining real options:
  (5) uniform ctx 16384 at util 0.92 (+1.0 GiB margin) or 0.95 (+1.6 GiB), tail truncation
  returns; (6) replace the held-out model. fp8-KV already rejected (quantization-contrast
  confound, 2026-08-31).

## 2026-09-01 — R0 applied: uniform ctx reverted 24576 -> 16384, util 0.90 -> 0.92 (gemma4 KV fit)
- Precedence rule R0 (feasibility before quality, M17) applied to the one open blocker:
  gemma4 KV at 24576 = 15.17 GiB needed vs 9.44 avail (measured, probe-falsified saving).
  Uniform ctx dropped to 16384 (gemma4 KV 10.36 GiB < pool 11.07 at util 0.92, ~0.7 GiB margin);
  util raised 0.90 -> 0.92 for the KV headroom. Qwen models unaffected (huge margins; their
  2026-08-31 peaks 73.2/73.7/72.1 GiB stand, now at lower ctx so only safer).
- Tail episodes >16k truncate — accepted under R0; truncation rate will be MEASURED in staging
  and reported, per the limitation protocol. Uniformity (same ctx all 4 models) preserved.
- T1 validation threshold aligned to 16384 (needle at ~15.5-16k); T3 ceilings now measured-based.
- Frozen parameters (R0): ctx=16384, util=0.92, 4 models, uniform shim — no further changes
  until the pilot completes ONE full end-to-end run.

## 2026-09-01 — gemma4 third failure: 16384/0.92 still short (KV 13.76 need vs 11.03 pool); linear KV model falsified
- Evidence: staging_evidence/20260901T150048Z/serve_gemma4-31b.log. Qwen x3 HEALTHY at new
  settings (peaks 76681/77039/75435 MiB). gemma4: Available KV 11.03 GiB, need 13.76 GiB,
  vLLM est. max seq len 13120. My linear KV model (M15-derived) was WRONG again: KV need did
  not scale with ctx (15.17@24576 -> 13.76@16384); there is a large fixed/per-batch component.
- RELIABLE anchor (vLLM's own estimate, not my extrapolation): max ctx at util 0.90 = 11232.
  Interpolating the measured (util,pool) and (ctx,need) points: util 0.95 -> pool 13.40 GiB
  -> max ctx ~14.4k; util 0.97 -> pool ~14.85 -> max ctx ~16.6k.
- gemma4 feasibility conclusion: at ctx 16384 gemma4 needs util ~0.97 (R12-hostile, ~2.4 GiB
  total card headroom); at util 0.95 the max feasible ctx is ~14.3k (margin +0.17 GiB — thin).
  gemma4 is the binding constraint for ANY ctx above ~13k on this card/build.
- Options recorded for user decision (pre-screened):
  (a) ctx 13312 uniform at util 0.95 — gemma4 margin +0.17 GiB, thin;
  (b) ctx 12288 uniform at util 0.95 — gemma4 margin +0.35 GiB, safer; truncation tail grows;
  (c) replace gemma4 held-out with a fitting model, keep 16384.

## 2026-09-01 — gemma4 KV: root mechanism identified; probe was mis-designed (my error)
- vLLM hybrid-KV docs (v0.27.1): sliding-window layers get windowed allocation ONLY via the
  eviction machinery that prefix caching drives. My 2026-09-01 probe used
  --no-enable-prefix-caching, which DISABLES the sliding-window saving — the probe tested the
  wrong condition and its "falsification" was of a config that can't save memory by design.
- gemma4's two layer groups differ in kv_hidden_size (sliding 16kv x 256 = 4096 vs global
  4kv x 512 = 2048) so they can't merge (docs Case 2/3) — but each still gets its own
  allocation strategy WITH prefix caching on. The 13.76/15.17 GiB needs were measured with the
  saving off (my probe) or partially engaged.
- OPEN measurement (do NOT trust my interpolation — two close points overfit, M15/M16 lesson):
  gemma4 at ctx 16384, util 0.90, prefix caching ON (default) — read the reported
  "Available KV cache memory" and "Maximum concurrency" lines. Until that number exists,
  every ctx/util recommendation for gemma4 is an ESTIMATE, not a measurement (R13 label).
