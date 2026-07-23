# S-09: Explicit Anti-Hallucination Guardrails Per LLM Role

## What It Is

`vinu_research` already has 7 distinct LLM call sites, each with its own system
prompt (generate, refine, risk-critic, diagnose, characterize, reflect, validate —
`llm.py`/`llm_generator.py`). That's already persona-like separation. What's
missing is what fincept-terminal's persona configs
(`ref-fincept-terminal/fincept-qt/scripts/agents/finagent_core/configs/
behavioral_finance_analyst_agent.json` and siblings) bake into every persona: an
explicit, per-role refusal/anti-hallucination instruction, e.g. "DO NOT hallucinate
numbers" (`behavioral_finance_analyst_agent.json:16`), alongside a mandatory
evidence-gathering framing and a fixed output schema.

## Why It's Required

Three of your seven prompts explicitly ask the LLM to reason about *numbers it
didn't compute itself*: `_diagnose_failure` asks for a root cause referencing
specific indicator behavior, `characterize_stock` asks for a stock profile, and
`_validate_idea` asks for a suitability judgment citing "evidence." None of the
current system prompts (`DIAGNOSIS_SYSTEM_PROMPT`, `STOCK_CHARACTERIZATION_PROMPT`,
`VALIDATION_SYSTEM_PROMPT` in `llm.py`) contain an explicit instruction against
fabricating specific numbers not present in the provided data — they ask for
structured JSON but don't guard against the model inventing a plausible-sounding
RSI value or p-value that wasn't actually in the prompt.

## Impact

- **If unfixed:** a diagnosis or characterization that *sounds* data-driven ("RSI
  never hits 30/70, stays in 40-60 range") could be entirely fabricated by the LLM
  rather than read from the actual `stock_profile`/`_feature_snapshot` passed in —
  and there's currently no way to tell the difference, since the output format is
  identical either way.
- **If fixed:** each prompt explicitly constrains the model to cite only figures
  present in its input, and the constraint is auditable (if the emitted JSON cites
  a number, it's checkable against the source data provided in that same prompt).

## How to Use Effectively

1. Add one line to each of the four data-referencing system prompts in `llm.py`
   (`DIAGNOSIS_SYSTEM_PROMPT`, `STOCK_CHARACTERIZATION_PROMPT`,
   `REFLECTION_SYSTEM_PROMPT`, `VALIDATION_SYSTEM_PROMPT`): "Only cite specific
   numbers that appear in the data provided above — do not estimate or invent
   values that weren't given to you." This is a one-line change per prompt, no new
   infrastructure.
2. This is cheapest to validate once **S-05**'s trace log exists — you'd be able
   to grep past diagnoses for numbers that don't appear in the corresponding
   `stock_profile`/`_feature_snapshot` input, i.e. actually measure hallucination
   rate before and after the guardrail.
3. Don't over-invest here beyond the prompt-level fix — a full grounding/citation-
   checking pipeline (verifying every number in the LLM output against the input)
   is more machinery than this system currently needs. The one-line guardrail is
   the right amount of effort for the current risk level (advisory diagnosis text,
   not something that directly executes trades).

## Implementation Hint — Where This Fits Today

**Entry point:** four module-level string constants in `llm.py` —
`DIAGNOSIS_SYSTEM_PROMPT`, `STOCK_CHARACTERIZATION_PROMPT`,
`REFLECTION_SYSTEM_PROMPT`, `VALIDATION_SYSTEM_PROMPT` (all added by P2/P4, all
plain triple-quoted strings). This is the lowest-effort suggestion in the entire
set — it's a one-sentence addition to four existing string constants, no code
logic changes, no new function signatures, nothing else in the call chain needs
to know this happened.

**Why this is feasible right now:** these four prompts already end with a
`Return JSON with this exact schema: {...}` instruction block — appending one
more line ("Only cite numbers that appear in the data provided above...") to each
is literally editing a string literal, not refactoring anything. There's no
prerequisite work.

**Suggested rollout order:** do `DIAGNOSIS_SYSTEM_PROMPT` first — it's the one
called most often in practice (every 0-trade iteration, per `loop.py:333-337`),
so it's the best candidate to sanity-check the guardrail actually changes model
behavior before copying the same line into the other three.

## Potential Bugs to Watch For While Testing

- **Over-conservative refusal instead of a better diagnosis.** Adding "don't
  invent numbers" can push the model toward returning an empty or unhelpfully
  vague `root_cause` when the input data is genuinely sparse, rather than
  reasoning as far as the data allows. Test on a case with deliberately thin
  input (e.g. a `stock_profile` with only 1-2 fields populated) and confirm the
  diagnosis is still *useful*, not just "safe but empty" — a guardrail that
  trades hallucination for uselessness isn't a net improvement.
- **No automated way to measure this without S-05.** "Did hallucination go down"
  isn't testable by unit test — it needs either a curated set of known-input/
  known-bad-output regression cases, or the trace log (S-05) to spot-check real
  runs. If S-05 isn't built yet, be explicit in the PR/change description that
  this was validated by manual spot-check on N runs, not by an automated test,
  so nobody mistakes "the prompt changed" for "the behavior was verified."
- **This is a prompt string change with no schema change** — low risk of
  breaking existing parsing, but still worth a quick regression pass confirming
  the four call sites still return validly-shaped JSON after the wording change
  (a longer/differently-worded prompt occasionally shifts a model's output format
  even when the schema instruction itself didn't change).
