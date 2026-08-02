---
name: full-plan
status: definition-phase
purpose: single source of truth for building a day-by-day historical replay of the real vinu-agent LLM decision loop over a real past month, so P&L and behavior can be checked before waiting for live/premarket trading days — what gets built, in which files, what "done" looks like, before any implementation starts
---

# 1-Month Agentic Replay — Plan (2026-08-03 draft)

**This is a definition document, not an implementation log.** Nothing
described here has been built yet. Same discipline as
`e2e-test-0731/full-plan.md` and `the-stage-2-claude/full-plan.md`: scope
and file targets fixed up front so an agent picking this up doesn't have
to re-derive architecture decisions.

## Why this exists

The user's question: instead of waiting for real calendar days to pass to
find out whether the agentic system (`vinu-agent`) trades well and adapts
correctly, can we place the agent at a real point in the past — say one
month ago — feed it exactly the news/analysis/price data that was
genuinely available at that moment (no lookahead), let it make real
decisions day by day through the LLM loop it would actually use live, and
see what money it would have made and how it behaved?

**Answer: yes, and most of the hard part already exists.** Historical
news, prices, and `vinu-initial-analysis` output (significance_score,
novelty_score, peer_relative_strength, regime features) are already
stored and queryable for any past date range — nothing new needed there.
What's missing is narrow and specific: (1) a way to make the agent
believe "now" is a past date and prevent it from querying past that date,
and (2) a way to fill its trade decisions against historical prices
instead of hitting Alpaca's real live/paper account. This plan defines
both, plus the orchestration to drive a full month and the reporting to
read the results.

**This is a different thing from `vinu-research`'s existing statistical
backtesting** (Sharpe/CAGR promotion bar, already real and enforced — see
`vinu_research/promotion.py`). That tests whether a *signal* is
statistically sound. This tests whether the *agent's actual reasoning* —
how it weighs significance_score against risk-budget tier, whether it
changes behavior after a loss, whether it uses the tools it has — would
have been profitable and sane, step by step, the same way a human PM
would be evaluated. Both are legitimate and this doesn't replace the
other.

## The five items — one-line summary, full detail in scope-responsibilities/

| # | Item | Where it lives | Status |
|---|---|---|---|
| 1 | Simulated clock + lookahead guard | `vinu-agent` (core: context, tools, session) | Not started |
| 2 | Historical-fill broker stub | `vinu-agent` (new `broker/historical_broker.py`), reuses `vinu-simulator`'s cost model | Not started |
| 3 | Day-stepper replay harness — stores thinking + response separately per day | New orchestration script, drives items 1+2 across the chosen month | Not started |
| 4 | P&L + decision-transcript reporting | Reuses `vinu_simulator.engine.metrics`, new report script | Not started |
| 5 | Behavioral rubric vs. premarket-readiness questions | Reads item 3's transcripts against `the-project-vision/the-premarket-agents-questions.md` | Not started |

Items 1-4 are infrastructure — build once, reusable for any future month,
not just this one. Item 5 is the actual payoff for the user's second,
earlier question (whether the agent can plan, adapt to losses, and
maintain risk discipline) — it's the same question, answered with real
transcripts instead of speculation.

## Important context already established — don't re-derive this

- **`vinu-simulator`'s `WeightSimulator` already solves T+1-safe fills**
  (`vinu-components/vinu-simulator/vinu_simulator/engine/simulator.py:106`
  — `ws_aligned.shift(1)`, with the comment explaining why: "a signal
  observed using data through day D can only be acted on starting day
  D+1"). The historical-fill broker (item 2) must follow the same
  discipline — fill at the next available bar after the agent's decision,
  never at the exact price that produced the decision. Don't reinvent
  this; reuse `vinu_simulator.engine.costs` (`AlmgrenChrissCostModel` /
  `FlatCostModel`) for slippage instead of a new cost model.
- **`vinu-agent`'s `Session` model already has a free-form `config: dict`
  field** (`vinu_agent/session/models.py:39`, persisted via
  `to_dict()`/`from_dict()`). This means the simulated-time flag for a
  session does **not** need a schema migration — store it as
  `session.config["as_of"]`, same pattern as any other per-session
  setting.
- **Tool instances already receive per-session attributes via
  `hasattr` injection**, not constructor arguments
  (`vinu_agent/tools/__init__.py:26-51` — `build_registry()` checks
  `hasattr(tool, "_session_id")` etc. after instantiating each tool and
  sets the attribute directly). The lookahead-guard clamp (item 1) should
  follow this exact pattern — add `_as_of = None` as a class attribute on
  each date-sensitive tool, let `build_registry` set it when present, so
  a normal (non-replay) session is completely unaffected by default
  (`_as_of is None` means "use real now," today's behavior, unchanged).
- **`AlpacaBroker` is instantiated inline inside `TradeTool.execute()`**
  (`vinu_agent/tools/trade_tool.py:69,162` — `broker = AlpacaBroker()`),
  not injected. Item 2 needs a small factory seam here so a replay session
  gets `HistoricalFillBroker` instead, without touching how a live session
  behaves.
- **Direction prediction does not work** (confirmed twice this project,
  rule-based sentiment and FinBERT, ~50% coin-flip on AAPL/TSLA/JNJ). If
  the replay shows the agent's decisions correlating with direction calls
  from `significance_score` or sentiment, that is the model doing
  something it has no right to do — flag it, don't quietly accept a lucky
  month as proof it works.
- **No premarket data exists anywhere in this stack** (see
  `the-project-vision/the-premarket-agents-questions.md`, Section 2).
  This replay uses regular-session daily/intraday bars — it does **not**
  and cannot test premarket-specific behavior. Item 5 must say this
  explicitly rather than imply the replay proves premarket-readiness.

## Data sources — what's available, what isn't (checked 2026-08-02/03)

- **News + prices**: full historical depth for AAPL/TSLA/JNJ back to
  2022-01-01 (JNJ's earliest news article is 2022-01-03, confirmed in
  `the-stage-2-claude/testing-status/significance-classifier-improvement/test-log.md`).
  A 1-month window anywhere in 2022-2026 is covered.
- **`vinu-initial-analysis` angle output** (significance_score,
  novelty_score, peer_relative_strength, regime_features): stored in
  Parquet via `AngleStorage`, queryable for any historical range via the
  existing `GET /analysis/angle/...` routes — same data the agent's tools
  already call live. No new backfill needed.
- **Options Greeks/IV** (`get_options_greeks` tool): live-snapshot only,
  no historical lookup at all (confirmed in `the-stage-2-claude/`). If the
  replay window is in the past, this tool must either be disabled for
  replay sessions or return an honest "not available historically" error
  — do not fake historical options data.
- **Exact window pick**: do not hardcode a start/end date in code before
  verifying real coverage. Query each ticker's actual data range first
  (`vinu-news`'s `backfill_status` endpoint per ticker, `vinu-stock-price`'s
  candle range) and pick the most recent fully-covered 20-23 trading-day
  window across AAPL, TSLA, and JNJ simultaneously — recommend the most
  recent complete calendar month before today so results are as
  relevant as possible, but verify, don't assume, that all three tickers'
  news and price data actually reach that far forward before committing
  to it.

## Execution order — recommended, not mandatory

1. **Item 1 first** (simulated clock + lookahead guard) — nothing else
   works without it, and it's the smallest, most contained change.
2. **Item 2** (historical-fill broker) — depends on item 1 only in that a
   replay session needs both wired together to be useful, but the broker
   code itself can be built and unit-tested independently.
3. **Item 3** (day-stepper harness) — depends on 1 and 2 both existing.
4. **Item 4** (reporting) — can be scaffolded in parallel with item 3,
   finalized once item 3 produces real transcripts.
5. **Item 5** (behavioral rubric) — last, strictly depends on item 3's
   real output existing; do not attempt to answer it speculatively.

## How to verify each item — general rule

Same rule as prior plans: verify against the real running
`vinu-components` stack, not synthetic fixtures alone. Sequence requests
to `news-api`/`initial-analysis-api` one at a time (prior crash
precedent, SQLite WAL fragility under concurrent load over a Windows
Docker bind mount — still applies). Every core-file change in items 1-2
touches code also used by real live/paper trading sessions — after each
change, re-verify a **normal, non-replay** session still behaves
identically to before (e.g. re-run the Stage 2 smoke test in
`the-stage-2-claude/testing-status/stage2-readiness-verification/`) so
this work never silently regresses the live path.

## Related documents

- [scope-responsibilities/](scope-responsibilities/) — one file per item,
  exact files to touch, function-level detail, expected output.
- [testing-status/](testing-status/) — one `test-log.md` per item, same
  convention as `e2e-test-0731/` and `the-stage-2-claude/`.
- [../the-project-vision/the-premarket-agents-questions.md](../the-project-vision/the-premarket-agents-questions.md)
  — the question set item 5 checks the replay transcripts against.
- [../the-stage-2-claude/full-plan.md](../the-stage-2-claude/full-plan.md)
  — sibling plan; item 2 here (historical broker) is architecturally
  separate from and does not touch that plan's item 3 (real paper-trading
  broker path) — replay sessions and live sessions must never share a
  broker instance.
