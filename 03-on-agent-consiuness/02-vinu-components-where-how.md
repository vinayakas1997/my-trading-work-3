---
name: vinu-components-where-how
status: audit
purpose: maps 01-quant-agent-qualities.md's three layers (data, consciousness, skills) onto the real vinu-components codebase — what exists and works, what's built but never consulted, what's genuinely missing. Every claim below is checked against the actual code/data this session, not inferred from file names.
---

# Where the Groundwork Actually Is, and Isn't

Read `01-quant-agent-qualities.md` first — this file assumes that
framework. Status tags used throughout:

- ✅ **exists and is actually used** — built, wired in, and confirmed
  exercised (either by code inspection of the call path, or by direct
  evidence from the 1-month replay's real transcripts).
- ⚠️ **built but dormant/unused** — the capability genuinely exists in the
  codebase, but nothing calls it, or the agent never chose to, or it's
  wired to nothing upstream/downstream. This is the most important
  category — it's easy to mistake "the code exists" for "the system does
  this."
- ❌ **missing** — not found anywhere in the codebase, confirmed by direct
  search, not just "I didn't happen to see it."

The honest headline: **the data layer is in genuinely good shape. The
skills layer has more real infrastructure than the 1-month replay ever
touched. The consciousness layer is almost entirely missing** — and that's
the layer that actually determines whether any of the rest gets used
correctly.

**This file is a snapshot audit — it stays accurate as long as nothing
below has actually been built.** `03-advanced-patterns-from-reference-
repos.md` already has a concrete, code-level answer for most of the ❌/⚠️
rows below (pulled from a real, working repo, not theory) — each such row
now has a "→ see 03" pointer. Read 02 for "is this true of our codebase
today," read 03 for "here's a working answer to copy." Once any of these
are actually implemented in `vinu-components`, the corresponding row here
should flip to ✅ with a new file/line citation — not be silently
forgotten in 03.

---

## 1. Data layer

| Need (from file 01) | Status | Where |
|---|---|---|
| Own true state, live not recalled | ✅ (live) / ❌ (replay) | `AlpacaBroker.get_positions()`/`get_account()` (`vinu-agent/vinu_agent/broker/alpaca.py:143-145`) hits Alpaca's real `/v2/positions` every call — always fresh in live trading. In replay, `HistoricalFillBroker` caches `last_close` only at fill time and never refreshes it (`historical_broker.py:107,178,189`) — confirmed frozen for 3+ weeks in the actual replay run. Live path is fine; replay path is a real, logged bug (`02-the-1-month-back-testing/testing-status/historical-fill-broker/test-log.md` Bug-2). |
| Price/volume/quotes, timestamped | ✅ | `vinu-stock-price` serves real OHLCV keyed by `bar_ts`, confirmed 2022→2026 coverage for AAPL/TSLA/JNJ. `stock_price_tool.py` reaches it correctly (post-fix). Timestamps exist on every row; nothing surfaces "staleness" as an explicit signal to the model, though — the raw material is there, the framing isn't. |
| Fundamentals/news, source-tagged, timestamped | ✅ | `vinu-news` articles carry `provider`, `tier`, `sort_ts`; `news_tool.py`/`fundamentals_tool.py` (yfinance) both work post-fix. Real depth: 16,616 articles, 2014→2026. |
| Structured log of past decisions + outcomes | ✅ **implemented** (`01-plan-and-implementations/03-structured-decision-journal.md`) | Reused `vinu-research`'s existing `HypothesisRegistry` rather than building a new store (it already existed with a status lifecycle + `invalidation_reason`, just aimed at research hypotheses, not trade theses). `trade_plan_tool.py`'s `_schedule_journal_write` now writes each generated trade plan into it (`status: testing`), and it's surfaced back to the agent every session via the ground-truth block (item 2). **Not yet confirmed**: whether a position closing actually writes the predicted-vs-actual comparison back — the debrief half (skills-layer row below) may still be open, verify before relying on it. |
| Regime/macro context | ✅ (data) / ⚠️ (usage) | `vinu-initial-analysis` computes and stores `regime_analysis` per symbol (confirmed real parquet output, 8 tickers). `generate_trade_plan` (`trade_plan_tool.py`) explicitly pulls `regime_analysis` as one of its inputs. The data and the plumbing exist — but in the actual 20-day replay, `generate_trade_plan` was **never called once**, so this regime data never actually reached a real decision. |
| Provenance/timestamp metadata per fact | ⚠️ | Raw data has timestamps (`bar_ts`, `sort_ts`, `created_at`). Nothing in `ContextBuilder` (`agent/context.py`) tags a message as "fetched this turn" vs. "recalled from history" — the model sees a flat list of strings either way. This is really a consciousness-layer gap wearing a data-layer costume: the provenance exists in the raw tool output, it just isn't preserved or distinguished once it enters conversation history. |

**Groundwork quality: solid.** The actual market/news/fundamentals data
pipeline is real, deep, and (after this session's fixes) functioning
correctly end to end. The gap here isn't "we need more data sources" —
it's "we need a structured decision-outcome record," which is a much
smaller, more targeted build than it might sound.

---

## 2. Consciousness / harness layer

This is where almost everything is either missing or unused.

| Need (from file 01) | Status | Where |
|---|---|---|
| Forced daily ritual (can't skip) | ✅ **implemented** (`01-plan-and-implementations/02-forced-ground-truth-injection.md`) | `GroundTruthInjector` (`vinu_agent/audit/ground_truth.py`) force-fetches fresh prices for held positions (and open theses from `HypothesisRegistry`) and injects a `<ground-truth>` block into `ContextBuilder.build_messages()` before every turn — not something the model can choose to skip. Preserved across compaction (`AgentLoop._auto_compact` now special-cases `_ground_truth_system_msg`). Unit-verified via the full test suite (224 tests passing); **not yet re-verified against a real replay** to confirm the specific 16-of-20-day dropout pattern can't recur — do that before calling this closed end-to-end. |
| Structured working memory (data, not prose) | ✅ **implemented** (same file as above) | The ground-truth block combines fresh price *and* open-thesis/invalidation status per held symbol in one injected block — the per-position structured record this row asked for is now read fresh every turn instead of recalled from prose. |
| Fact vs. belief distinction | ✅ **implemented** (`01-plan-and-implementations/01-fact-verification-audit.md`) | `FactAuditor` (`vinu_agent/audit/fact_audit.py`) regex-extracts symbol-tied numeric claims from the final answer and verdicts them `Verified`/`Stale`/`Fail` against the session's actual tool-result history, logged in `result["audit"]` (`agent/loop.py::_build_result`). Currently flag-and-log, not a hard block, per the item file's own guidance. **Not yet re-verified**: whether this would actually have caught the specific JNJ `$162.45` fabrication if replayed — that's the concrete test to run before trusting the false-positive/false-negative rate. |
| Risk governor above the reasoning loop | ✅ (partial) / ⚠️ (partial) | This is the one area with genuinely good existing groundwork: `TradingMandate` (`broker/mandate.py`) + `OrderGuard` enforce `max_position_pct`, `max_order_value`, `max_daily_orders`, `max_capital_utilization_pct`, `max_symbol_concentration_pct`, `max_pairwise_correlation`, `require_confirmation` — **at order time, outside the model's reasoning**, confirmed a real, working pattern (the exact "governor above the loop" file 01 asks for). Also real: the -20% portfolio circuit breaker (`vinu-portfolio/circuit_breakers.py`), started by default via `entrypoint.sh`. **But**: the graduated risk-budget tiers (-1%/-2%/-3%, `vinu-portfolio/risk_budget.py`) are computed on every status call and **read by nothing** — a governor whose early-warning tiers are dead code; only the outermost hard stop actually bites. And `ShadowEvaluator` (`vinu-live/vinu_live/shadow_evaluator.py`) — real code that would gate a strategy on actual paper-trading performance before trusting it further — is fully dormant, confirmed nothing calls it. |
| Calibrated self-doubt / anti-fabrication | ✅ (fabrication-catching half) / ❌ (genuine deferral half) | The fabrication-of-facts half is now implemented — `FactAuditor` (row above) flags a stated number with no matching tool call this session. The other half — the agent genuinely saying "I don't have enough here for a real view" instead of always producing a plausible answer — remains unsolved, on purpose: **nobody in any of the six reference repos solved this structurally**, and it was explicitly kept out of scope in `01-plan-and-implementations/AGENTS.md` rather than bolted on as a rushed 5th item. Stays real and open. |
| Real escalation path | ✅ (mechanism) / ⚠️ (unverified edges) | `ConfirmationHandler` (`broker/confirmation.py`) + `require_confirmation` mandate flag + Telegram/Discord channels (`channels/discord.py`, `channels/telegram.py`) are real and wired — a genuine human-in-the-loop mechanism exists, 5-minute timeout. Kill switch (`broker/kill_switch.py`) also real, file-based. What's unverified (per `the-project-vision/the-premarket-agents-questions.md` Section 6, still open as of this writing): whether the kill-switch file's location is actually durable across a container restart, and who gets notified when it fires. Good bones, some real edges never load-tested. |
| Session hygiene that doesn't erode the ritual | ⚠️ | `AgentLoop._apply_context_layers` (`agent/loop.py:290-314`) is a genuinely well-built three-tier compaction system (microcompact → context-collapse → LLM-summarized auto-compact). It's not the cause of the replay's tool-call dropout (token counts never got remotely close to triggering it in a 20-day/40-message run). The actual gap: `AgentLoop` is instantiated fresh every single day (`session/service.py::_run_with_agent`, one new `AgentLoop()` per attempt), so `_previous_summary` never persists cross-day anyway — there's no ritual yet to erode, but there's also no cross-day summarization happening at all, just raw message accumulation up to `store.get_messages(limit=50)`. |

**Groundwork quality: thin, with one real bright spot.** The order-time
risk governor (`TradingMandate`/`OrderGuard`/circuit breaker) is exactly
the right pattern, already built, already enforced outside the model's
own judgment — reuse it as the template for whatever forces the daily
ritual. Everything else in this layer — the actual "always check first,
never fabricate, know what's stale" discipline — does not exist yet in
any form, soft or hard.

---

## 3. Skills layer

| Need (from file 01) | Status | Where |
|---|---|---|
| Falsifiable thesis with invalidation criteria | ⚠️ | **Better groundwork than expected**: `generate_trade_plan` (`tools/trade_plan_tool.py`, backed by `vinu-research/trade_plan_authoring.py`) explicitly produces "entry checklist, profit-booking tranches, and invalidation/exit rules," pulling regime data, factors, backtest validation, and news sentiment together. This is close to exactly what file 01 describes. It was simply **never called** in the actual replay — the one real trade was entered on ad hoc SMA/RSI reasoning typed directly into the final answer, with no formal invalidation rule attached to the order at all. |
| Portfolio-aware position sizing | ✅ | `max_capital_utilization_pct`, `max_symbol_concentration_pct`, `max_pairwise_correlation` in `TradingMandate`/`OrderGuard` — genuine whole-book checks, not just single-trade limits. Real groundwork. |
| Execution judgment (stops, order type) | ⚠️ | `AlpacaBroker.submit_order()` (`broker/alpaca.py:151-`) natively supports `stop_loss_price`/`take_profit_price` — real bracket/OTO order support, confirmed in code. Capability exists; nothing requires or even nudges its use. The replay's one real order was a naked market buy, no stop attached — confirmed directly in the transcript (`submit_order({"order_type":"market","qty":100.0,"side":"buy","symbol":"AAPL"})`, no stop/target fields present). |
| Debrief / predicted-vs-actual comparison | ❌ | Directly depends on the missing structured decision log (data layer, above). No mechanism anywhere closes this loop. |
| Cross-signal reading with correct proven boundaries | ✅ (as a finding) | This is the one place where the project has already done real, hard-won work: rule-based sentiment and FinBERT sentiment were **directly tested twice** and confirmed ~50/50 (coin-flip) for predicting price *direction* on AAPL/TSLA/JNJ. `significance_score` is explicitly documented as predicting *magnitude/surprise*, not direction. This is genuine, verified negative-result groundwork — the risk isn't that this analysis is missing, it's that nothing structurally stops a future strategy rule from misusing `significance_score` for direction anyway (a prompt-level warning exists in the questions doc; nothing code-level enforces it). |

**Groundwork quality: more real than the replay's behavior suggested.**
The tools to do this properly — `generate_trade_plan` with real
invalidation rules, portfolio-aware sizing, bracket orders — already
exist. The 1-month replay didn't fail because these tools are missing.
It failed because nothing *required* using them, which is a consciousness-
layer problem wearing a skills-layer costume.

---

## Net assessment

Building more skills right now would be solving the wrong problem — the
skills layer already has more real infrastructure (`generate_trade_plan`,
bracket orders, portfolio-aware sizing, a verified sentiment-doesn't-
predict-direction finding) than the actual replay ever exercised. The
order-time risk governor (`TradingMandate`/`OrderGuard`) proves this
project already knows how to build a "governor above the reasoning loop"
correctly — it just hasn't been applied to the daily-ritual problem yet.

**The concrete, highest-leverage next build is entirely in the
consciousness layer** — and as of `03-advanced-patterns-from-reference-
repos.md`, it no longer needs to be designed from scratch. Superseding
what this file originally proposed here (a retry-based forced-verification
nudge): Vibe-Trading already has a cleaner, working answer — inject fresh
ground-truth data before reasoning starts instead of trying to detect and
retry a skipped check after the fact (03 point 1), a real audit tool that
catches fabricated numbers before they reach a final answer (03 point 3,
the single highest-priority pull), and a structured hypothesis/thesis
journal that gives `generate_trade_plan`'s already-real invalidation rules
somewhere persistent to live (03 point 2). See 03's "Recommendation"
section for the priority order. Everything else — more data sources, more
analysis angles, more tools — is real but secondary until this layer
exists.
