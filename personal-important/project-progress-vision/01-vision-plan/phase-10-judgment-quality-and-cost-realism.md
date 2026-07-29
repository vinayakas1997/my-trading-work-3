# Phase 10 — LLM Judgment Quality Control & Cost Realism

Status: **not started** · Depends on: Phase 1, Phase 4, Phase 9 (for calibration data) · Blocks: —
(Advanced vision — see [02-advanced-vision.md](02-advanced-vision.md))

## What it is

Two smaller but important trust-building upgrades:

**10a — LLM judgment calibration tracking.** Stages 1–3 lean heavily on LLM verdicts: the risk
critic's PASS/REFINE/STOP (`vinu-research/vinu_research/loop.py`'s `_risk_critic`), the
comparative critique's improvement angles (Phase 4's `ComparativeCritic`), and playbook
narrative content (Phase 5). None of these are currently checked for self-consistency or
tracked against outcomes. Two concrete additions: (a) self-consistency — re-run the risk
critic's LLM-enhancement step on the same input more than once and require agreement before
trusting an upgrade from REFINE to PASS/STOP; (b) outcome calibration — once Phase 9's shadow
and live re-validation data exists, retroactively check whether strategies the critic passed
actually held up live, and track this as a calibration metric over time (e.g. "of strategies
passed in the last 6 months, what fraction survived their first re-validation check?").

**10b — Cost realism.** Confirm that Stage 0's Monte Carlo and all backtest metrics are computed
net of realistic trading costs — slippage (the `execution-model` skill already documents
fixed/VWAP/TWAP slippage models and transaction-cost tables), fees, and short-borrow cost for
short positions — not gross returns. This is the classic way a backtest silently lies: a
strategy's Sharpe can look strong gross and evaporate once realistic costs are applied,
especially for higher-turnover strategies.

## Impact

**Before this phase:** LLM verdicts are trusted at face value with no tracking of whether
they're actually predictive, and there's no explicit confirmation that validation numbers
reflect realistic trading costs rather than idealized fills.

**After this phase:** The team has a running calibration score for how much to trust the
critic's PASS verdicts, and confidence that a strategy's validated Sharpe reflects what it
would actually earn after costs, not a gross number that won't survive contact with a real
broker.

## Where changes occur

- `vinu-research/vinu_research/loop.py` — `_llm_enhanced_check` (the LLM-enhancement step
  inside `_risk_critic`): add a self-consistency re-check before allowing a verdict upgrade
  (e.g. call twice, require the same `verdict_upgrade` both times, or fall back to the
  rule-based verdict on disagreement).
- New calibration-tracking table/query, likely in `vinu-research/vinu_research/storage/sqlite_backend.py`,
  joining `research_runs`' recorded verdicts against Phase 9's live/shadow outcome data once
  that exists — a periodic report (`fraction of PASS verdicts that survived first
  re-validation`) rather than a live gate.
- `vinu-simulator/vinu_simulator/service.py` / `vinu_simulator/models/simulation.py` — audit
  that `transaction_cost_pct`/`slippage_pct`/`slippage_model` are always populated with
  realistic defaults (not zero/omitted) whenever Stage 0's validation runs, and that short
  positions' borrow cost is included if the strategy allows shorting (`allow_short` field
  already exists on `SimulateRequest`/`CustomSimulateRequest` — confirm borrow-cost modeling
  exists or needs adding).
- `vinu-agent/skills/execution-model/SKILL.md` — already documents the slippage/cost
  methodology; confirm the pipeline's default parameters actually match what this skill
  recommends rather than drifting from it, and update the skill doc if the implementation
  reveals gaps.

## How to test it

- Unit test: feed `_llm_enhanced_check` a mocked LLM client that returns different
  `verdict_upgrade` values on repeated calls for the same input, and confirm the self-consistency
  check refuses to upgrade the verdict.
- Unit test: confirm Stage 0 validation calls always pass non-zero, non-default
  `transaction_cost_pct`/`slippage_pct` unless explicitly overridden, and that a strategy's
  reported Sharpe changes (typically decreases) when realistic costs are applied vs. a
  zero-cost control run — this proves costs are actually being applied, not just present as
  unused parameters.
- Once Phase 9 exists: an integration test computing the calibration metric against a seeded
  set of past verdicts and known synthetic outcomes, confirming the fraction calculation is
  correct.
