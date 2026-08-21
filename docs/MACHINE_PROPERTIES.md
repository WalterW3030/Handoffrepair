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
| /dev/vda1 | 96G | 86G | **11G** | 89% | **/** (root — nearly full!) |
| tmpfs | 709G | 250M | 709G | 1% | /dev/shm |
| tmpfs | 5.0M | 0 | 5.0M | 0% | /run/lock |
| tmpfs | 709G | 0 | 709G | 0% | /run/qemu |
| /dev/vda16 | 881M | 183M | 637M | 23% | /boot |
| /dev/vda15 | 105M | 6.2M | 99M | 6% | /boot/efi |
| /dev/vdb | 6.3T | 5.6T | **429G** | 94% | **/ephemeral** (only big writable disk) |
| tmpfs | 142G | 400K | 142G | 1% | /run/user/1000 |

### GPU (from approval records — Day 0 Record 4 §remaining, Record 9 H1, Staging Approval Ledger)
| Property | Value |
|---|---|
| Machine spec (approved) | **1× H100 SXM5 80GB**, ≥16 vCPU, ≥128GB RAM, ≥500GB NVMe |
| vLLM arch target | sm_90 (H100) — matches pinned container's arch list |

### Runtime environment (user-reported 2026-08-20, check answers A2–A5)
| Property | Value |
|---|---|
| Conda env python | **3.12** ✅ (within required 3.10–3.12) |
| Docker | Engine Community **29.1.3** (API 1.52, containerd 2.2.1, runc 1.3.4) — client+server respond **as user, no sudo** ✅ (docker group OK) |
| DockerRootDir | `/var/lib/docker` — **>40 G free** (user-verified) ✅. Note: earlier `df` showed `/` at 11 G avail — so `/var/lib/docker` is on another mount or storage was expanded after approval; staging re-records `df` and will catch any discrepancy |
| Machine network | `huggingface.co` → **HTTP/2 200** ✅; `registry-1.docker.io` reachable ✅ (weight/image pulls possible machine-side) |

### Consequences (derived, binding for all planning)
- **Everything large lives on `/ephemeral`**: HF cache (`HF_HOME=/ephemeral/$USER/hf`), repo clone, docker data if movable, all logs/evidence. Root `/` has 11 G free — the ~230 GB of weights + ~20 GB container image cannot touch `/`.
- **429 G avail vs plan**: weights ≈230 G + vLLM image ≈20 G + logs/evidence ≈10 G ≈ 260 G → fits with ~170 G headroom. Tight but OK. `/ephemeral` is likely wiped on machine release (name suggests it) → evidence must be uploaded/exported after each phase.
- Large RAM (≥700 G by tmpfs sizing) — host-side processing unconstrained.

## 2. Version pins this machine must satisfy (from repo)
| Component | Pin |
|---|---|
| ToolSandbox | commit 165848b9a78cead7ca7fe7c89c688b58e6501219 |
| vLLM image | vllm/vllm-openai@sha256:0a51ea5b…bfd967 (v0.27.1, CUDA 13.0.2 user-space, sm_90) |
| Models | Qwen3-32B 9216db57 · Qwen3-8B b968826d · RedHatAI/Llama-3.3-70B-Instruct-FP8-dynamic f50dbad2 · google/gemma-4-31B-it 842da379 |
| Weights | 39-file SHA-256 lock (`configs/weight_sha256.lock`) |
| Host python deps | per `scripts/setup_machine.sh` (polars==0.20.31, pydantic==2.7.4, openai==1.17.0, …) |

## 3. Open checks — remaining
All six original checks are now **answered** (recorded above). Remaining unverified items, in staging order:
1. **Driver vs container CUDA**: pinned vLLM image is CUDA 13.0.2 user-space; driver 570.195.03 supports max CUDA 12.8. CUDA 13 normally wants driver ≥580; on datacenter GPUs the container's `cuda-compat` may bridge this, but it is **not guaranteed**. Definitive test (staging_collect.sh runs it first, auto-stops):
   `docker run --rm --gpus '"device=0"' <pinned vllm image> nvidia-smi`
   If that errors with a CUDA driver mismatch → STOP; we then decide between (a) cuda-compat, (b) re-pinning to a CUDA-12.8-based vLLM image (formal lock change).
2. **gemma-4 license acceptance** on HuggingFace (user action, web).
3. **RAPID_API_KEY** obtained and set on the machine (main run only).

## 4. Change log
- 2026-08-20 — initial record from user paste; rules R1–R3 established.
- 2026-08-20 — GPU spec recovered from approval records (H100 SXM5 80GB; rule R6 created from this miss); A2–A5 check answers recorded: conda py3.12, Docker CE 29.1.3 no-sudo OK, /var/lib/docker >40G free, HF+Docker Hub reachable.
