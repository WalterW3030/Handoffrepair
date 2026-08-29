# Execution Rules (always-on)

Binding on every execution step of the HandoffRepair pilot, in this sandbox and on the GPU machine. R1–R3 set by the user 2026-08-20; R4–R7 added 2026-08-20. Companion file: `Machine Properties.md`.

## R1 — Property awareness
- Always be aware of the recorded machine properties (driver, CUDA, disks, versions) and of every package/model/container version pinned in the repo.
- For anything not recorded or not sure: **check it first, or ask the user to check** — never guess. Open checks are listed in `Machine Properties.md` §3.

## R2 — Avoid sudo (amended 2026-08-20 per user)
- Never put sudo in scripts; always exhaust no-sudo alternatives first (user-space paths, env vars, rootless runtimes, group permissions).
- If sudo is genuinely necessary: present the exact minimal command to the user — **the user runs it themselves**.
- **Every necessary sudo use must be reported**: logged in `Machine Properties.md` change log with the command and why it was necessary. (Report #1: `sudo mkdir -p /ephemeral/hr`, 2026-08-20 — no user-writable dir existed on the only big disk.)

## R3 — Exactly 1 GPU (amended 2026-08-28: always check availability first)
- All commands, scripts, and configs use exactly one GPU — never multi-GPU, no tensor/pipeline parallelism, no code that enumerates or splits across GPUs.
- **Before every GPU run, check which GPU is actually free**: `nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv`. This is a **shared 8-GPU machine** — another tenant's process held ~33 GiB on cuda:0 and killed our staging (real traceback 2026-08-28). Never hardcode device 0.
- Use the freest GPU (scripts auto-select it; override with `GPU_ID=n`). As of 2026-08-28, GPUs **5, 6, 7 are free** (user-reported) — but re-check every time; occupancy changes on a shared machine.
- Memory sizing must fit one GPU; if no single GPU has enough free memory, that's a STOP — wait or report, never span GPUs.

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

## R8 — Evidence via the repo's `evidence/` folder (amended 2026-08-28: mandatory for logs)
When a log, evidence bundle, or error output is needed for checking, **never paste it into chat — always push to the repo's `evidence/` folder** and I read it from GitHub:
- **Mandatory for ALL log/error files, even short ones** — logs grow unpredictably; pushing avoids truncation, formatting loss, and chat bloat. Pasting is only acceptable for ≤5-line status strings.
- Command pattern:
  ```bash
  git pull --no-rebase origin master    # always first — remote may have my commits
  cp <file(s)> evidence/
  git add evidence/ && git commit -m "evidence: <what>" && git push origin master
  ```
- Large tarballs (>~25 MB): tell me first (GitHub file-size limits); we split or use a release.
- The repo `.gitignore` keeps `staging_evidence/` raw dirs and bulk tarballs out of git by default — copy the *specific* file needed into `evidence/`.
- Applies to all future file-checking tasks, not just staging.

## R9 — Evidence before theory; break loops by widening, not repeating
Added 2026-08-22 after the qwen3-32b crash-loop failure (4 rounds, zero real logs, wrong OOM theory).
- **Never assert a cause without evidence.** State it as a hypothesis with what would confirm/refute it. Do not present a guess as a diagnosis.
- **On any error, search first** (web + the actual logs/data) for the *full* space of plausible causes — not just the first one that comes to mind. Rank them by evidence, not familiarity.
- **If the same fix is tried twice and the problem persists, STOP repeating it.** That is a loop. Break it by (a) getting the missing evidence first, and (b) deliberately looking *outside* the current assumption (different component, different layer — e.g. config/arg/entrypoint, not just memory/model).
- **Verify the evidence channel actually works before trusting it.** If a diagnostic file is supposed to contain the answer, confirm it is non-empty and non-stale *before* concluding anything from it. (We trusted a 65-byte "No such container" stub as if it were a real crash log — for 4 rounds.)
- **When a hypothesis fails, say so explicitly, drop it, and record what the evidence actually shows** (e.g. `exit_code=1, oom_killed=false` ⇒ config/arg error, *not* OOM).

## R10 — No over-promising; capture the signal at its source, not through a proxy
Added 2026-08-22 after the same loop persisted post-R9 (user: "you kept looping on similar behavior… untrustworthy… never really break").
- **No confident-but-unverified language.** Never say "this command gets the real error" / "one command to fix" / "must work now". State the hypothesis, the test, and what each outcome would mean. Report probability, not certainty.
- **A diagnosis is only as good as its weakest capture step.** Before trusting any observation, trace the *full chain* that produced it (run → detect → capture → file → read). A failure anywhere in that chain can manufacture a plausible-looking artifact that is NOT the real signal. (Our "crash log" was actually the *error message of our own `docker logs` probe* — "No such container" — not the crash.)
- **Capture output at the source, not through a removable proxy.** For a container/process that may die: redirect its stdout/stderr to a file *at launch* (or read the json-file log path via `docker inspect {{.LogPath}}`), never rely on a post-hoc read of an object that can disappear (a dead container, a removed name) before you read it.
- **When the same symptom recurs, re-derive from first principles instead of re-applying the last fix.** Ask: what *mechanism* produces exactly this observation (this exit code + this empty log)? Enumerate ALL mechanisms that fit before choosing an action.

## R11 — Estimate runtime; long commands go to tmux background
Added 2026-08-28 per user instruction.
- **Before giving the user any command, estimate its expected running time.** If it is expected to take **> 10 minutes** (model downloads, weight loads, staging, main runs), **say so explicitly and provide the tmux form** so the user can run it in the background and disconnect safely.
- Standard pattern for long commands:
  ```bash
  tmux new -s <name>        # run inside, detach with Ctrl+B then D
  tmux attach -t <name>     # reattach later to check
  # or fully detached:
  tmux new -d -s <name> 'bash <script> 2>&1 | tee <logfile>'
  tmux capture-pane -t <name> -p | tail -30   # check progress without attaching
  ```
- Always pair a long command with a way to check progress later (log file path or tmux capture command).

## R12 — Compare alternatives on experiment criteria before choosing; check the whole plan's machine cost with headroom
Added 2026-08-28 per user instruction (after llama-70b-fp8 didn't fit at any usable context length).
- **Before choosing between design options** (model swap, context-length change, util change), produce a **comparison on the criteria that matter to the experiment** (task capability, tool-calling, reasoning depth, context fit, license/access, precision) — including the **consequence of each option on experiment validity** — then recommend. Never present a single option as the answer.
- **Never size to the machine's limit.** When estimating GPU memory, context length, or any resource: use the model's **actual spec sheet** (params, dtype, layers, KV-head count, attention type) to compute cost, then **require ≥ 10–15% free headroom** after weights + KV cache + activation margin. A config that fits only at 95%+ utilization is a failed design, not a tight one.
- **Check the ENTIRE plan, not one model.** Before finalizing any serving/staging/main-run config, compute the cost for **every** model/pair in the pilot AND any follow-on phases (held-out eval, Day-2 audit, main run) against the recorded machine spec — one model fitting does not imply the plan fits.
- Record the comparison and the headroom math in `Machine Properties.md` before implementing the chosen option.

## R13 — Full parameter & workload analysis at DESIGN time, before any machine run
Added 2026-08-28 per user instruction (after context-length and model-fit failures surfaced mid-staging, not at design).
- **At experiment DESIGN time (before any GPU/staging run), analyze EVERY model and EVERY parameter that significantly affects performance or validity** — grounded in researched data (benchmark papers, model cards, spec sheets), not assumptions.
- This includes, minimum: context-length requirement from the *benchmark's actual trajectory lengths*; per-model memory (weights+KV+activation from real specs); tool-calling/reasoning capability per model; decoding parameters (temperature, max_tokens, penalties); and the workload's token/turn profile.
- **Record the analysis and the resulting parameter choices in the repo BEFORE implementing**, so choices are justified by data and auditable.
- The trigger for this rule is the *design* step — never let a parameter reach staging untested-by-analysis. (We let max_model_len=8192 and a 70B model reach staging without checking ToolSandbox's real ~11.6k-token episodes or the 70B's memory fit. Both failed. This rule exists because of that.)

## R14 — No fabricated structure: every enumerated item must be independently defensible
Added 2026-08-29 per user instruction (after C3/C4 "choices" were presented whose alternatives
were negligence foils no competent researcher would pick — see METHODOLOGY_MISTAKES.md M11/M12).
This is the integrity rule behind R9-R13: it governs the SHAPE of deliverables, not their content.
- **Pre-register before analyzing.** When a deliverable requires an enumerated structure
  (choices, options, causes, risks), first write the raw item list, then analyze each item,
  then present. Never construct items backwards from a preferred conclusion.
- **Defensibility test (mechanical, per item):** for each presented option, state the
  criterion under which a competent researcher would pick it over the others. If no such
  criterion exists, the item is a foil — delete it or fold it into the dominant option.
- **Empty is a valid answer.** "There is exactly one real decision here" or "there are no
  real choices — everything else is determined" is a complete, correct deliverable. A list's
  length carries zero credit. Never pad a list to match the shape of the request.
- **Distinguish the three output classes explicitly in the deliverable itself:**
  (a) items already fixed (bad parameters — applied without asking, listed for audit);
  (b) items with genuine trade-offs (presented for decision, each with defensibility criterion);
  (c) open risks (things neither fixable nor choosable — listed as risks, not disguised as choices).
- Root literature: Frankfurt (On Bullshit — output shaped to fit the occasion, indifferent to
  whether it is genuine); Krakovna et al. (specification gaming — literal spec met, intent
  defeated); Kalai et al. 2025 (evaluations that penalize abstention produce guessing —
  a forced non-empty list is such an evaluation); MASK/Ren et al. 2025 (honesty is a separate
  axis from accuracy and does not scale with capability).

## Standing pre-existing rules (unchanged)
- No GPU command without approval logged in the Staging Approval Ledger (staging approved 2026-08-18; main run still gated).
- Never move/overwrite tag `pilot-freeze-v1`. Never commit secrets. GitHub PAT is disposable — scrub after use. HF token read-only.
- No per-episode manual correction. Never fabricate data, evidence, or citations.
- self_flight self-check protocol stays always on (instruction declaration per task).
