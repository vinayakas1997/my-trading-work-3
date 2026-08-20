---
task: 08-live-llm-validation-tests.md
status: complete
---

# Status: task 08 — validate prompt-dependent behavior against a real LLM, not just mocks

## What I did

- **`vinu-agent/tests/test_live_llm_validation.py`** — NEW live-LLM smoke suite, env-gated
  (`RUN_LIVE_LLM_TESTS=1`), so it is excluded from the default fast/CI run and runnable on demand.
  It loads the REAL prompts from `teams/research/agents/idea_generator` and
  `teams/screener/agents/angle_synthesizer`, talks to the REAL configured model
  (`VINU_LLM_BASE_URL` / `VINU_LLM_MODEL`, defaulting to the production `http://localhost:8009/v1` /
  `qwen36-35B`), and records raw model outputs (not just pass/fail) to
  `vinu-agent/tests/live_llm_outputs/{idea_generator,angle_synthesizer}.md`.
  A pre-flight reachability check skips cleanly (never errors) when the model endpoint is down.

  Tests:
  1. `idea_generator` recipe-first: a simple fast/slow SMA-crossover tuning ask (a recipe genuinely
     covers it) → model must output a `RECIPE:` choice + `PARAM_GRID`, grounded in the real
     `list_recipe_details()` catalog and real angle data.
  2. `idea_generator` exception path: a pre-market order-book-imbalance ask (no recipe covers it) →
     model must explicitly say "no recipe fits" and fall back to raw Python with `generate_weights`.
  3. `angle_synthesizer` consensus: one realistic mixed run (agree pair, diverge pair, `row_count=0`
     pair) → model must report agree / diverge / insufficient_data matching the deterministic
     `compare_angles` results.
  4. `angle_synthesizer` all-angles-empty → model must state plainly that 0 of 28 angles have data.

## What was actually run (evidence)

- Production endpoint check first: `http://localhost:8009/v1/models` (qwen36-35B) responded at session
  start but was **down/unmanaged** by the time the live run started — no llama.cpp server process or
  startup script exists in the repo to bring it back up.
- Ran the suite against the reachable **real local model**: `glm-4.7-flash:q4_K_M` via the local ollama
  server (`http://localhost:11434/v1`, OpenAI-compatible). **All 4 tests passed** (~4.5 min).
  Re-running against qwen36-35B when it's up is one env-var line:
  `RUN_LIVE_LLM_TESTS=1 VINU_LLM_BASE_URL=http://localhost:8009/v1 VINU_LLM_MODEL=qwen36-35B pytest ...`

- Actual recorded model outputs (worth reading — `vinu-agent/tests/live_llm_outputs/`):
  - Recipe case: `RECIPE: crossover` + a 3-point `PARAM_GRID`, with real grounded reasoning ("regime_analysis
    shows bull, trend_lifecycle uptrend … crossover is the exact implementation").
  - No-recipe case: explicit "no recipe fits … none support time-of-day filtering or order-book imbalance",
    then coherent raw Python `class Strategy(BaseStrategy).generate_weights(...)` using only allowed
    indicator columns (`volatility_20d`) — genuine exception-path behavior, not a forced fit.
  - Consensus case: correctly reported **Agree** (arima 0.021 vs chronos 0.015, same direction),
    **Diverge** (regime_analysis bear vs trend_lifecycle uptrend), **Insufficient data** (kronos
    row_count 0), all citing the real values.
  - Empty case: "0 of 28 angles have data."

## Alignment with plan / acceptance criteria

- Live-LLM test suite exists, excluded from default CI runs (`4 skipped` in the fast suite), runnable on
  demand ✓
- Both behaviors run against a real model at least once, results documented with actual model output
  recorded ✓ (recorded files under `vinu-agent/tests/live_llm_outputs/`)
- No failures found on this model — no test loosening needed; both prompt behaviors held up in practice.
- Traceability: each recorded run now includes the model/base_url header.

## Notes

- The task's plan step "run against whichever provider/model this project uses in production" was
  honored where possible: the suite defaults to the production qwen36-35B config, and the live run that
  succeeded used the reachable local real model with the model identity recorded. The production
  qwen36-35B server being transient/unmanaged is itself a real gap worth noting (a future task could
  package it as a managed service).
- The tool-call layer (compare_angles calling, recipe catalog fetching) is covered by the existing
  deterministic tests; this suite validates the prompt-following layer (decision + verdict reporting)
  that mocks cannot.