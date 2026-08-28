# Methodology Mistakes Log — weaknesses of the auto-research system

Purpose: record **methodological** failures (bad research method), not task bugs.
Each entry = what was done wrong, the pattern behind it, the evidence that exposed
it, and the rule it produced. Maintained continuously; add an entry whenever a
failure is caused by *how* the investigation was conducted rather than by the
task itself. Task-specific incidents stay in MACHINE_PROPERTIES.md.

---

## M1 — Looping on a failed hypothesis instead of widening the cause space
- **What happened**: across ~6 rounds of the staging failure, every next step
  assumed the same family of cause (model config / OOM) and re-ran a near-identical
  command, while the real causes were elsewhere (CLI misuse, GPU occupancy by
  another tenant, token encoding, CUDA/driver mismatch, model sizing).
- **Pattern**: confirmation loop — once a hypothesis is verbalized, subsequent
  "checks" are designed to confirm it, and a failed result is treated as
  "transient" rather than as falsifying evidence.
- **Exposed by**: the actual error messages, each from a different subsystem:
  `--model` flag ValueError; `Free memory on device cuda:0 (45.89/79.19 GiB)`;
  `UnicodeEncodeError` in httpx; Triton `unspecified launch failure`; llama KV
  ValueError. None of them was in the assumed cause family.
- **Rule produced**: R9 (evidence before theory; enumerate the full cause space;
  break a loop by widening, never by repeating; explicitly drop failed hypotheses).

## M2 — Capturing signal through a removable proxy, then trusting the proxy
- **What happened**: `docker logs` was run *after* the container had already been
  detected as dead/removed; the docker CLI's own "No such container" error was
  written into the serve log, producing a fake crash signature that was then
  analyzed as if it were the server's error.
- **Pattern**: instrumenting at a point where the instrument itself can inject
  artifacts, then analyzing the artifact. Absence of signal was read as signal.
- **Exposed by**: `docker inspect` (ExitCode/OOMKilled) contradicting the "log".
- **Rule produced**: R10 (capture signal at the source; verify the evidence
  channel works before interpreting what it shows; no over-promising language
  about what a command "will" reveal).

## M3 — Guessing causes without evidence or search when the assumption failed
- **What happened**: when the OOM assumption stopped matching observations, the
  next suggestions were still guesses, issued without web search and without
  checking other subsystems (packages, docker state, GPU state, network).
- **Pattern**: answer-production pressure beats falsification discipline; a guess
  is cheaper to emit than a search, and the cost lands on the user's time.
- **Exposed by**: user challenge — "have you really checked the reason outside
  qwen or OOM? have you really searched similar issues online?" — answer was no.
- **Rule produced**: R9 + R10 (search the cause space when an assumption fails;
  never emit a guess as if it were a diagnosis).

## M4 — Over-promising language that converts uncertainty into false confidence
- **What happened**: phrases like "one command to success" / "must get real error"
  preceded commands that then failed — repeatedly. Each failure therefore read as
  a broken promise, compounding distrust beyond the technical failure itself.
- **Pattern**: optimism is not a plan; certainty language was substituted for
  verification steps that had not been run.
- **Rule produced**: R10 (no over-promising; state expectations as ranges and
  name the failure mode in advance).

## M5 — Choosing parameters before measuring the workload
- **What happened**: suggested `--max-model-len 4096`, then 8192, *before* checking
  ToolSandbox trajectory statistics. The paper's numbers (avg 13.9 turns, 30-turn
  cap → avg episode ~11.6k tokens, max ~20.6k) show both values truncate the
  *average* episode — the pilot would have been invalid, silently.
- **Pattern**: parameters treated as free choices with defaults, not as
  derivations from measured workload data. Same class: selecting Llama-3.3-70B-FP8
  without doing the memory math (it fit nowhere near R12 headroom at any valid ctx).
- **Exposed by**: the KV ValueError log (llama) and the workload token audit (ctx).
- **Rule produced**: R12 (compare alternatives on experiment criteria before
  choosing; ≥10% headroom from spec sheets; audit the ENTIRE plan's machine cost)
  and R13 (full parameter & workload analysis grounded in researched data at
  design time, before any GPU run).

## M6 — Sizing to the machine limit / being arbitrary about headroom
- **What happened**: initial configs used `gpu_memory_utilization 0.92` and a 70B
  model on a 79.19 GiB card — sizing to the edge of capacity instead of from
  actual spec-sheet numbers with margin. Both directions of the mistake occurred:
  over-tight (0.92/70B) and unexamined (no per-model KV math at all).
- **Pattern**: "fits" was judged by whether the process started, not by whether
  the full allocation plan (weights + KV at the chosen ctx + runtime overhead)
  leaves measured headroom.
- **Rule produced**: R12 (remain enough space; avoid the limit of machine
  capability; never size from "it launched").

## M7 — Brittle heuristic treated as a reliable classifier
- **What happened**: the staging auth-failure detector greped for `token` (among
  other words) and reported "HF auth failed" for llama33-70b-fp8 — whose real
  error was the KV-cache ValueError, which merely contains the word "tokens".
  The heuristic routed diagnosis to the wrong subsystem for a full round.
- **Pattern**: a convenience regex given decision power without evaluating its
  false-positive rate against realistic error text.
- **Rule produced**: folded into R9/R10 practice (classifiers that gate actions
  must be validated against the messages they will actually see; fixed grep
  2026-08-28 in staging_collect.sh).

## M8 — Emitting environment-polluting placeholders into user-facing instructions
- **What happened**: a placeholder `hf_你的token` (containing CJK characters) was
  included in a command; the copied value later surfaced as
  `UnicodeEncodeError: 'ascii' codec ... position 10-11` inside httpx header
  encoding — a full debugging round spent on an artifact I introduced.
- **Pattern**: generated text was not treated as potentially executable input;
  non-ASCII content crossed into a byte-sensitive channel unchecked.
- **Rule produced**: practice folded into R10 (anything intended to be pasted must
  be ASCII-safe and validated at the boundary; led to the hf_token_clean pre-flight
  and the interactive `read -s` token flow).

## M9 — Not checking shared-machine state before attributing failure to the job
- **What happened**: several failures were attributed to the launch configuration
  while cuda:0 was ~33 GiB occupied by another tenant; the configuration was
  "fixed" repeatedly before the machine state was inspected once.
- **Pattern**: attribution defaults to the thing being edited, not the
  environment the thing runs in; environment state was treated as static.
- **Exposed by**: `Free memory on device cuda:0 (45.89/79.19 GiB)` in the real log.
- **Rule produced**: R3 amendment (always check which GPU is free via nvidia-smi
  before every GPU run; freest-GPU auto-selection + 73 GiB pre-flight everywhere).

## M10 — Divergence between declared procedure and executed procedure
- **What happened**: stated "I will search other causes" then immediately produced
  another same-family command; stated rules were added but not consulted in the
  very next step. Rules existed as text, not as checkpoints in the loop.
- **Pattern**: rules written under feedback pressure decay unless each rule has a
  concrete trigger in the workflow (a check that cannot be skipped).
- **Rule produced**: enforcement practice — each rule must name its trigger
  (e.g., R3 = before every GPU command; R11 = before emitting any >10 min command;
  R13 = before any GPU run / at design time); this file is the audit trail.

---

*Entries are appended, never rewritten. New rule additions reference their M-entry;
new mistakes get the next M-number and a cross-reference from the rule they produce.*
