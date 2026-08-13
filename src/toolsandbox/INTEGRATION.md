# ToolSandbox Integration (A6) — pinned findings, verified 2026-08-11

**Pinned upstream commit:** `165848b9a78cead7ca7fe7c89c688b58e6501219` (2025-11-06, repo HEAD at clone).
License: Apple open-source (see LICENSE in repo). Clone at Day 0 must `git checkout` this commit.

## Structure relevant to the pilot

- Scenarios: `tool_sandbox/scenarios/{single_tool_call, multiple_tool_call, multiple_user_turn,
  insufficient_information}_scenarios.py` — each exposes `named_*_scenarios(preferred_tool_backend)`
  returning `{name: Scenario}`. Rough definition counts found: 19 / 54 / 28 / 28.
- Evaluation: `tool_sandbox/common/evaluation.py` — `Milestone` / `Minefield` classes with DAG edges
  and `SnapshotConstraint` similarity (our `src/scoring/dag.py` mirrors this semantics and was
  verified against hand-computed cases in A5).
- Tools: `contact, messaging, reminder, setting, user_tools, utilities` — all local, stateful,
  database-backed (self-contained ✅).
- **`rapid_api_search_tools.py` (`search_stock`, `search_lat_lon`) — calls external web services ❌.**
  Referenced from 3 scenario files (36 references). → **P3 exclusion rule** implemented in
  `select_scenarios.py`: any scenario whose tool set touches that namespace is dropped.

## External dependencies to neutralize (P3)

1. **rapid_api_search_tools** → scenario exclusion (above).
2. **User simulator** — `tool_sandbox/roles/openai_api_user.py` is an external OpenAI API role
   (and the paper reports simulator hallucination). Pilot replaces it with a **local vLLM-served
   model, seed 101** (`configs/seeds.yaml`), all simulator outputs logged; scoring never uses
   simulator judgment — milestone/minefield DAG only.
3. **Agent roles** — `hermes_api_agent.py` (Hermes prompting) matches vLLM's Hermes tool parser;
   use it as the reference role implementation for our open models. API-based roles
   (anthropic/openai/gemini/cohere/mistral/gorilla) are unused in the pilot.

## Day-0 steps

1. `git clone … && git checkout 165848b9a…`
2. `pip install -e .` on the GPU machine
3. `python src/toolsandbox/select_scenarios.py --repo <clone> --out configs/episodes_pilot.yaml`
4. Record the resulting pilot episode set in `configs/episodes.yaml` (replacing `TBD_AT_DAY0_SELECTION`)
   **before** applying tag `pilot-freeze-v1`.
