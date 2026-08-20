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

## 3. Open checks — user, please run and paste back (no sudo needed)
1. **GPU model & count**: full `nvidia-smi` output (the paste had only the header). Need: GPU name, memory per GPU, how many GPUs. All sizing assumed 1× ~80 GB (e.g. H100) — must confirm. Rule R3: we will use exactly one regardless.
2. **Driver vs container CUDA**: pinned vLLM image is CUDA 13.0.2 user-space; driver 570.195.03 supports max CUDA 12.8. CUDA 13 normally wants driver ≥580; on datacenter GPUs the container's `cuda-compat` may bridge this, but it is **not guaranteed**. Definitive test (staging_collect.sh runs it first):
   `docker run --rm --gpus '"device=0"' <pinned vllm image> nvidia-smi`
   If that errors with a CUDA driver mismatch → STOP; we then decide between (a) cuda-compat, (b) re-pinning to a CUDA-12.8-based vLLM image (formal lock change).
3. **Docker without sudo**: does `docker version` work as your user (i.e. are you in the `docker` group)? Per Rule R2 we will not sudo-install it. If not working, options: ask your admin to add you to the docker group, or rootless podman/docker with storage on /ephemeral.
4. **Docker Root Dir + its free space**: `docker info --format '{{.DockerRootDir}}'` then `df -h` on that path. Needs ≥40 G free for the vLLM image. If it points at `/` (11 G free), per Rule R2 alternatives: set `XDG_DATA_HOME=/ephemeral/...` with rootless docker, or ask admin to relocate — not a silent sudo step.
5. **Outbound network on the machine**: `curl -sI https://huggingface.co` and `curl -sI https://registry-1.docker.io` — confirms weight/image downloads are possible from the machine (they are blocked from this chat sandbox, which is why downloads happen on your side).
6. **python3 version on host**: `python3 --version` (setup assumes ≥3.10).

## 4. Change log
- 2026-08-20 — initial record from user paste; rules R1–R3 established.
