# Functional and non-functional requirements (one file, one section per service)

Written 2026-10-07 from the code and the running stack. "Must" is the requirement. **Gap** marks something the requirement asks for that the system does not yet do or has not yet proven. Numbers marked **(to measure)** have no measured value yet; they must be measured and written in, not guessed.

## 0. Rules that apply to every service

### Functional (global)
- G1. Equities only; broker is Alpaca **paper** only.
- G2. The system works 24 hours, five days a week. Session names and hours come from one definition (`vinu_infra/sessions.py`); no service may hard-code its own market hours.
- G3. Every data read that feeds a decision is point-in-time safe (no future data).
- G4. A strategy trades only in sessions it has been approved for, and only where data and evidence exist.
- G5. Every rejection is recorded with its reason (no silent drops).

### Non-functional (global)
- N1. **Fail closed on the trade path:** if the order guard, strategy store, kill switch or broker clock cannot be read, the order is refused.
- N2. **Fail open only on optional enrichment** (news, reflection hints), and say so in the response.
- N3. Every service answers `GET /health`; a service that is up but cannot reach what it needs reports unhealthy.
- N4. Secrets only in `vinu-components/secrets/`, never in logs, responses or the repo.
- N5. A code fix is not done until the image is rebuilt, the container recreated, logs checked, and a test that fails on the old code exists (problem log).
- N6. Shared settings (session, bar size, ticker, interval) must agree across services; see section 14 "Change-impact list".
- N7. Timeouts, queue sizes and retry counts are written in config, not in code constants buried in a file **(to measure and list per service; today they are scattered)**.

---

## 1. llm-gateway (:8099)
**Purpose:** the single door to the language models (local `hindsight-llm` and any external one). Every AI call in the system goes through it.
### Functional
- `POST /v1/chat/completions` (OpenAI-style), `GET /v1/models`, `GET /llm/queue`, `GET /llm/history`.
- Queues requests, records each call (who, model, prompt size, answer, time, error) in history.
### Non-functional
- Must return a clear error (not hang) when the model is down or slow; callers must be able to tell "model failed" from "model said no".
- Must never log API keys.
- Calls are serialised per model; queue depth is visible at `/llm/queue`.
- Limits: timeout per call, max queue length, max prompt size **(to measure)**.
- **Gap:** no requirement yet for what the agent does when the gateway is down for hours (see diagram 6).

## 2. stock-api (:8081, routes under `/stock`)
**Purpose:** price history and live quotes. Owns the candle store.
### Functional
- `GET /stock/candles/{symbol}` with `interval` and `session` (regular / extended / all / list); sessions are applied to 1-minute bars **before** aggregating to larger bars.
- `POST /stock/candles/batch`, `GET /stock/quote/{symbol}`, `GET /stock/catalog[/{symbol}]`, `GET /stock/events/{symbol}`.
- `POST /stock/backfill/trigger` (`from_year`, `refresh`), ingest, watchlist.
- Providers: Alpaca main feed (IEX, regular session) and overnight feed (`boats`, from 2024-09-16, 15-minute delay).
- Default session comes from `VINU_STOCK_DEFAULT_SESSION` (regular), so callers that do not ask are unchanged.
### Non-functional
- Point-in-time clamp (`as_of`) on candles and ticker routes; headers say when data was clamped, empty, or gapped.
- A backfill is idempotent: re-running adds only missing bars (merge by timestamp).
- The overnight request window must stop 16 minutes before now (the feed answers 403 otherwise).
- Must never present thin data as complete: a session with too few bars is reported as such.
- **Gap:** pre-market and after-hours are thin (IEX only; SIP not permitted). Holidays not modelled.
- Limits: candles per request, request rate to Alpaca **(to measure)**.

## 3. news-api (:8080)
**Purpose:** collects, dates and scores news per ticker.
### Functional
- Feeds, ingest, backfill, search, `GET /ticker/{symbol}`, `GET /articles/since`, high-impact list, watchlist, threads.
- Keeps `published_at` separate from `ingested_at` and flags estimated publish times.
### Non-functional
- News is optional input: if it fails, analysis continues and says news was missing (N2).
- Point-in-time: an article is visible only from its publish time.
- Sentiment scoring (FinBERT) may be slow; it must not block ingest.
- Limits: poll interval, articles per request **(to measure)**.

## 4. features-api (:8082, `vinu-tools`)
**Purpose:** the indicator and factor library (28 indicators) as a service.
### Functional
- `GET /catalog`, `/factors`, `/presets`; request/run endpoints that compute indicators on given bars.
- One blessed entry: `apply_indicators()`; nobody deep-imports an indicator module.
### Non-functional
- Deterministic: same bars in, same numbers out.
- A short or empty series returns an explicit "not enough data", never zeros that look like values.
- Indicators must not look ahead.

## 5. initial-analysis-api (:8083)
**Purpose:** per-ticker analysis ("angles"): regime, trend lifecycle, news-price causality, signal evidence and others.
### Functional
- `POST /run/{ticker}`, `GET /angle/{name}/{ticker}`, `GET /angles`, coverage, latest run, story, drawdown, correlation.
- Writes signal-evidence to research.
### Non-functional
- **In scope: 12 angles** (27 registered; 11 model angles skipped on purpose while models are off; 4 overlapping angles switched off). Coverage is always "n of 12"; see `00-project-understanding/analysis-angles-in-scope.md`.
- Every angle result states the data window it used and when it was computed.
- An angle that cannot compute says so; the others still return.
- **Gap (24 hours):** angles are computed on regular-session bars; per-session regime tags are not produced yet.

## 6. screener-api (:8095)
**Purpose:** picks the stocks to work on (rules and rankers; the top 10).
### Functional
- Rules and rankers CRUD, `POST /screener/rankers/{id}/rank`, `GET .../latest`, churn, rejected samples with reasons.
- Hard filters (price, dollar volume, minimum history bars) before scoring.
### Non-functional
- Same inputs give the same top list; a ticker that drops out is recorded with the reason.
- Must not return a ticker without enough history to be tested.
- The list is the planner's source each cycle; if the screener is down the planner uses the last list and says so.

## 7. quant-core-api (:8084, simulator under `/simulator`, strategy engine)
**Purpose:** runs a backtest of given strategy code on given bars.
### Functional
- `POST /simulator/simulate`, `POST /simulator/simulate/custom` (code, symbols, dates, interval, **session**), results: metrics, trades, equity (full timestamp for intraday), weights.
- Metrics annualised by the hours actually traded (e.g. 15m: 26 bars/day regular, 96 over 24 h).
- Same question (config hash including session when not regular) gives the stored result.
### Non-functional
- Strategy code runs in a sandbox (AST guard); no file, network or process access.
- Deterministic and reproducible: same code, data and config give the same result.
- A different session or bar size must never reuse another run's result.
- Limits: run time, bars per run, code size **(to measure)**.

## 8. research-api (:8087)
**Purpose:** decides whether a strategy is good. **The code decides PASS, never the AI.**
### Functional
- Validates one strategy on all bar sizes (1d, 1h, 15m, 5m as available), under regular hours and all 24 hours; keeps per-bar evidence.
- Promotion bar: enough trades (**30**), deflated Sharpe, holdout, stress test, PBO (waived only when too few results to compute it, and the waiver is stored).
- Per-session breakdown and risk hints (`session_stats`): approved sessions need at least **200** bars and a positive result.
- `POST /research/validate-code`, artifacts, promote, hypotheses, evidence, decay, graveyard, sweeps.
- Up to **3** attempts per ticker; each retry gets the failure reasons.
### Non-functional
- A pass must be reproducible from the stored evidence (`bar_interval`, `bar_evidence`, `trading_sessions`).
- A strategy that fails statistically is rejected even if it makes money in the sample; the bar is never lowered to produce a pass.
- Research on a bar size with missing or thin data is refused with a data reason, not scored.
- Each run is checkpointed so a restart is visible, not silent. **Gap:** a deploy kills an in-flight research run.
- Limits: run time per attempt, simulations per attempt **(to measure)**.

## 9. portfolio-api (:8090) and the fate keeper
**Purpose:** the risk gatekeeper and capital allocator: how much each approved strategy may use.
### Functional
- `/portfolio/weights`, `/daily-allocation`, `/risk/status`, `/not-funded` (with reasons), `/evaluate-batch`.
- Circuit breakers, drawdown actions (ok / halve / flat / halt), correlation-aware sizing, netting of opposite signals.
- **Gap:** the allocation does not yet carry the strategy's approved sessions or size multipliers; today only the order guard reads them (from the strategy store). The requirement is that the allocator also uses them.
### Non-functional
- Deterministic and independent of the AI's confidence; the AI cannot override a halt.
- A strategy that is not funded is recorded with the reason.
- **Gap:** gatekeeper and allocator have been run only on the synthetic test chain, never on a real strategy (none has passed research yet).

## 10. live-api (:8091)
**Purpose:** turns approved targets into orders and watches them: live decisions, reconciliation, execution.
### Functional
- `POST /live/cycle`, `/feedback/cycle`, decisions, executions, journal, snapshots, slippage (TCA), lockouts, emergency flatten/resume.
- Poll bars on candle close; track each strategy through its stage; reconcile the book with the broker.
### Non-functional
- Checks circuit breakers before every order; repeated drift between target and actual raises an alert.
- Emergency flatten must work even if other services are down.
- **Gap:** live feedback (fills back into research) is not yet proven on a real strategy. Live overnight bars arrive 15 minutes late.

## 11. agent-api (:8086): planner, research team, order guard, broker link
**Purpose:** runs the AI teams, and is the only path to the broker.
### Functional
- Planner: one research run per ticker per cycle; research team writes the strategy, backtest runner tests it, the validator checks the bars.
- `POST /agent/broker/order` through the **order guard**: kill switch, session check from the broker clock, strategy-session approval, active-strategy check, mandate (`allowed_sessions`, limits), session size multiplier.
- Orders: outside regular hours only day LIMIT with `extended_hours=true`; overnight only if the asset is `overnight_tradable`.
- Identify an order by `id`, `client_order_id`, `asset_id`; statuses pending_new, new/accepted, filled or canceled; fills also in account activities.
### Non-functional
- **Fails closed** (N1). Proven on a real paper round trip (overnight SPY, 1 share).
- The AI never calls the broker directly.
- Every order attempt, allowed or refused, is logged with the guard code.
- Limits: orders per day, max order value, max position per symbol come from the mandate **(to list)**.

## 12. reflection-worker (no HTTP port) and hindsight-llm (:8092)
**Purpose:** learns from outcomes: loss attribution, threshold calibration, a synthesis that the planner reads.
### Functional
- Writes beliefs and synthesis; serves `GET /reflection/synthesis/latest|pending`, `/beliefs/notable` (read-only).
### Non-functional
- Never places orders or touches the kill switch.
- Optional input to research (N2).
- **Gap:** the agent's reflection tool points at a service address with no HTTP port; the link is unproven.

---

## 13. Whole-system requirements for the 24-hour loop
- W1. The loop (screen, analyse, write, research, retry, fate keeper, paper order, feedback) runs without a person for a full day and night and records each stage.
- W2. Between two cycles nothing is lost on restart: runs, strategies, orders and evidence are persisted.
- W3. A deploy must not silently destroy work; a killed research run must be visible and restartable.
- W4. The scoreboard (`scripts/pipeline_health.py`) must show, per line: PROVEN on the real system / TESTED only synthetic / UNPROVEN. A line moves to PROVEN only after a real run.
- W5. Today: 8 of 16 lines PROVEN on the real system; gatekeeper, allocator and order guard tested only on the synthetic chain; paper order at the broker proven by the overnight round trip; live feedback unproven; **0 real ACTIVE strategies**.

## 14. Change-impact list (these must agree; change one, check all)
| Setting | Places that must agree |
|---|---|
| session | `vinu_infra/sessions.py`, stock-api candles filter and default, simulator request + config hash + annualisation + equity timestamps, research validation sets and stored `trading_sessions`, order guard and mandate `allowed_sessions`, size multiplier |
| bar size (interval) | stock-api aggregation, simulator annualisation, research `bar_validation` and stored `bar_interval`, strategy code assumptions (one bar size per strategy test), promotion bar |
| ticker | screener list, stock catalog/history, analysis coverage, research artifact universe, portfolio funding, order guard symbol limits |
| minimum trades / bars | research promotion bar (30), session approval (200), data problem checks |
| order type | broker submit, order guard, trade tool, strategy-session rules |

Each row becomes a test or a script check when the problem log is built.
