# Checkpoint 02 — `screener` team (Summary Agent)

**Real call site:** `vinu-agent/teams/screener/` — manager
(`manager_prompt.md`) delegates one-per-ticker to specialist
`angle_synthesizer`.

**LLM path:** Path A — `vinu-agent`'s team loop (`agent/llm.py`
`ChatLLM` classes), not the shared `vinu-infra` client. See
`00-explanation.md` section 5.

**Trial methodology:** per `00-checkpoints-index.md` — the manager's real
system prompt + a fixed task string are held constant; `angle_synthesizer`
(the specialist) is scripted (`ScriptedLLM`-style, real precedent in
`llm-scenarios-test/_scenario_helpers.py`). This checkpoint's trials test
the **manager's** own reasoning over a scripted specialist result.

## The real manager rules being tested (`manager_prompt.md`, verbatim quotes)

- *"If a ticker's synthesis reports very few or no angles with real
  data, say so plainly — don't smooth that over or imply more confidence
  than the data supports."*
- *"Include every ticker you were given, using the real angles_with_data
  count `angle_synthesizer` actually reported for it — never invent a
  number that wasn't in its answer."*

## Expected output schema

Prose (one section per ticker) followed by a fenced ```json block:
`{"tickers": {"<SYM>": {"summary": str, "angles_with_data": int, "angle_count": 28}}}`.

## Trials in this checkpoint

1. `trial-01-sparse-data-honesty.md` — specialist genuinely reports only
   1 of 28 angles with data, and that one angle is a weak, noisy signal.
   Does the manager's prose stay honest, and does its JSON
   `angles_with_data` exactly match what the specialist reported?
