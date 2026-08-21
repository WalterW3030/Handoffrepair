# Environment Specification — Python versions & required packages
2026-08-20. Sources: (a) **verified by execution** — the exact set installed in a clean sandbox that passed the real 18/18 ToolSandbox dry-run and the 1,180-run soak; (b) pilot repo source scan; (c) items marked **[verify on machine]** are from ToolSandbox's own metadata, which cannot be re-fetched from this sandbox (GitHub egress currently blocked) — the machine-side import smoke test in `setup_machine.sh` is the decisive check (Rule R1: no guessing).

## 1. Python version
| Where | Version | Basis |
|---|---|---|
| pilot env on GPU machine | **3.10, 3.11, or 3.12 — NOT 3.13+** | polars==0.20.31 ships one abi3 wheel (cp38-abi3, works ≤3.12); pydantic-core==2.18.4 wheels stop at cp312 (both verified on PyPI 2026-08-20). Conda's default python is often 3.13 → use `conda create -n handoffrepair python=3.12` |
| Host system python | unknown — **open check #6** (`python3 --version`) | used only to create the env |

Rule R4: everything runs inside an isolated env — **either** the project venv (`<repo>/.venv`) **or** a dedicated conda env (user's machine uses conda); `setup_machine.sh` auto-detects and records the interpreter in `env.sh` (`PILOT_PYTHON`).

## 2. Required packages (venv)

### Version-pinned (hard pins — changing any of these is a lock change)
| Package | Pin | Why (from code) |
|---|---|---|
| openai | **1.17.0** | vLLM server is OpenAI-API-compatible; pilot `vllm_client.py` uses the openai client. Pinned old on purpose: newer openai + pydantic conflict (circular import) — found empirically |
| pydantic | **2.7.4** | ToolSandbox core models (Scenario/ExecutionContext) are pydantic; 2.11.4 broke with openai 1.17.0 — pinned down empirically |
| pydantic-core | **2.18.4** | must match pydantic 2.7.4 |
| polars | **0.20.31** | ToolSandbox database layer (`tool_sandbox/common/…`) — API changed across versions; **critical pin** |
| pytest | 9.1.1 | repo `requirements-lock.txt` (CPU-verifiable harness) |

### Unpinned (latest fine — verified working)
| Package | Why (from code) |
|---|---|
| phonenumbers | ToolSandbox contact/messaging tools validate phone numbers |
| pycountry | ToolSandbox utilities (locale/country handling) |
| geopy + geographiclib | ToolSandbox location tools (lat/lon distance) |
| holidays | ToolSandbox reminder/holiday tools |
| pint (+ flexcache, flexparser) | ToolSandbox unit-conversion utilities; flexcache/flexparser are pint's parser deps (needed explicitly in a clean env) |
| absl-py | ToolSandbox logging/flags (import name `absl`; **package name is `absl-py`, not `absl`**) |
| distro | ToolSandbox platform detection |
| tqdm | ToolSandbox progress bars |
| numpy | pilot repo: `src/analysis` bootstrap CIs |
| PyYAML | pilot repo: all configs (`yaml` import throughout `src/`) |
| huggingface_hub[cli] | weight downloads at pinned revisions (`hf download`) |

### Never installed
- vllm / torch / cuda python packages in the venv — GPU serving is **only** the digest-pinned container (`vllm/vllm-openai@sha256:0a51ea5b…`), per repo design.
- API-client SDKs for anthropic/cohere/mistral etc. that ToolSandbox's `pip install -e .` would pull — the pilot never uses those roles (`INTEGRATION.md`); we install via PYTHONPATH + the explicit list above instead, which is smaller and was verified sufficient by the real dry-run.

## 3. Install commands (what `scripts/setup_machine.sh` already runs — shown for transparency)

**Conda path (user's machine):**
```bash
cd /ephemeral/hr/Handoffrepair
conda create -n handoffrepair python=3.12 -y    # NOT 3.13 — see §1
conda activate handoffrepair
python -m pip install --upgrade pip
python -m pip install \
  openai==1.17.0 pydantic==2.7.4 pydantic-core==2.18.4 polars==0.20.31 \
  phonenumbers pycountry geopy geographiclib holidays pint \
  flexcache flexparser absl-py distro \
  numpy tqdm pyyaml "huggingface_hub[cli]" pytest==9.1.1
export TOOLSANDBOX_REPO="$(pwd)/ToolSandbox"
export PYTHONPATH="$(pwd)/ToolSandbox:${PYTHONPATH:-}"
```
(venv path is identical except `python3 -m venv .venv && source .venv/bin/activate` replaces the conda lines. **Do not mix**: with conda active, use `python -m pip`, never a bare `pip` that might belong to another env.)
Followed automatically by the import smoke test (fails loudly if anything is missing) and `pip freeze > env_freeze.txt` (goes into the staging evidence bundle).

## 3b. Troubleshooting (from user report 2026-08-20)
- **`ssh-keygen … -N ""` → "option requires an argument -- N":** the empty passphrase argument was lost in copy-paste (markdown may render curly quotes). Type it manually with straight ASCII quotes, or simplest: **omit `-N` entirely and press Enter twice** at the passphrase prompts:
  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/handoffrepair_deploy
  # Enter passphrase (empty for no passphrase):  <Enter>
  # Enter same passphrase again:                 <Enter>
  ```
- **`pip install` fails in conda:** most likely the conda env is Python **3.13** — the pinned wheels stop at 3.12 (§1). Check `python --version`; if 3.13, recreate with `python=3.12` as above. If it still fails on 3.12, paste the full error output here — do not improvise around it.

## 4. Providing secrets — RAPID_API_KEY and GitHub access

### RAPID_API_KEY (needed for main run only — 11/78 scenarios)
ToolSandbox's RapidAPI tools read it from the **environment variable `RAPID_API_KEY`** at call time.
1. Get a free key at rapidapi.com (subscribe to the APIs the tools use, e.g. the geocoding/holiday APIs used by `search_location_around_lat_lon` / `search_holiday`).
2. Provide it as an env var on the machine — **never paste it into the repo or this chat**, never commit it:
   ```bash
   echo 'export RAPID_API_KEY=your_key_here' >> ~/.bashrc   # or your shell profile
   ```
   `staging_collect.sh` already records only whether it is **set** (`yes/NO`), never the value.
3. Before the main run I'll add a one-line key probe (one cheap API call) so a bad key fails fast instead of mid-run.

### GitHub access to the repo (push is currently blocked — old PAT rejected)
Two options, in order of preference:
- **A. SSH deploy key (recommended, no sudo, reusable):** on the machine:
  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/handoffrepair_deploy -N ""
  cat ~/.ssh/handoffrepair_deploy.pub   # paste this into GitHub → repo Settings → Deploy keys → Add (allow write access)
  git clone -c core.sshCommand="ssh -i ~/.ssh/handoffrepair_deploy" git@github.com:WalterW3030/Handoffrepair.git
  ```
  Then pushes from the machine work without any token in URLs or chat.
- **B. Fresh fine-grained PAT:** GitHub → Settings → Developer settings → Fine-grained tokens → access to this repo only, `Contents: read/write`. Paste it **in this chat only if you accept it is disposable** (same handling as before: used in a temporary remote URL, scrubbed immediately, revoked by you after the RC tag push). Never stored in repo config.

If the repo is actually public-readable, cloning needs no token at all — only pushes do.

## 5. Change log
- 2026-08-20 — **pin fix**: pydantic-core 2.18.2→**2.18.4** (pydantic 2.7.4 hard-requires ==2.18.4; 2.18.2 was a transcription typo, caught by user's pip run). Verified via PyPI: openai 1.17.0 needs pydantic<3,>=1.9.0; pydantic-core 2.18.4 wheels cp38–cp312 (no cp313 → 3.12 stays required).
- 2026-08-20 — initial; dep set verified against clean-env dry-run/soak evidence; ToolSandbox setup.py re-check deferred to machine (egress blocked here).
