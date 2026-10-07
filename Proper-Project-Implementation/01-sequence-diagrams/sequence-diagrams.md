# Sequence diagrams (8), traced from the vision

How to use: take any functional question from the vision (for example "who stops a bad order?" or "what happens at night?"). The coverage matrix at the end names the diagram that answers it. If a vision case has no diagram, the matrix shows it as a gap.

Arrows come from the connection manifest `vinu-infra/pipeline_edges.yaml` (41 entries) and from the code. Notes in each diagram say what is **default off**, what is a **known gap**, and the **status on the real system**:
- PROVEN = ran on the real stack and the values were checked.
- TESTED = ran only in tests, or only on the synthetic planted-edge chain.
- UNPROVEN = never run end to end.

Diagrams are Mermaid. In VS Code use the "Markdown Preview Mermaid Support" extension, or paste a block into mermaid.live.

---

## D1. Data inflow (prices, overnight bars, news, features)
Answers: where does data come from, how is each session covered, how is the future kept out.
Vision: A1, A14, B1, B6 (#19), D3.1.

```mermaid
sequenceDiagram
    autonumber
    participant AL as Alpaca (IEX and overnight feed)
    participant ST as stock-api 8081
    participant NW as news-api 8080
    participant FT as features-api 8082
    participant C as Any consumer
    ST->>AL: bars, regular session (IEX), per symbol and year
    ST->>AL: bars, overnight session (feed boats, 15 min delay, window ends 16 min before now)
    AL-->>ST: 1-minute bars
    ST->>ST: merge by timestamp into the candle store, record catalog and gaps
    NW->>NW: poll feeds, keep published_at apart from ingested_at, score sentiment
    C->>ST: GET candles symbol, interval, session, as_of
    ST->>ST: filter by session on 1-minute bars, THEN aggregate to the bar size, clamp to as_of
    ST-->>C: bars plus headers (clamped, empty, gap count, cache age)
    C->>FT: indicators on those bars (apply_indicators)
    FT-->>C: indicator series, or "not enough data"
    C->>NW: GET ticker news as of a time (optional input)
    NW-->>C: articles visible at that time
```
Status: PROVEN for stock candles and the overnight backfill (150 symbol-years). Gap: pre-market and after-hours bars are thin (IEX only). Holidays not modelled.

## D2. Discovery and analysis (top 10, then analysis)
Answers: how the top 10 are picked and what is known about each before a strategy is written.
Vision: A1, A2, A18 (selectivity funnel), A13 (analogues), B1, B5 #5, B6 #18.

```mermaid
sequenceDiagram
    autonumber
    participant SC as screener-api 8095
    participant PL as agent planner worker
    participant IA as initial-analysis-api 8083
    participant ST as stock-api
    participant NW as news-api
    participant RS as research-api 8087
    PL->>SC: top list (ranker latest), opt-in per config
    SC->>ST: history for hard filters (price, dollar volume, min history bars)
    SC-->>PL: ranked tickers plus rejected samples with reasons
    PL->>PL: keep top 10, one research run per ticker
    PL->>IA: run angles for ticker (regime, trend lifecycle, news-price causality, signal evidence)
    IA->>ST: bars
    IA->>NW: news (optional)
    IA->>RS: signal evidence write (trigger, outcome)
    IA-->>PL: angle results, each with its data window and time computed
    RS->>RS: evidence into the hypothesis registry (evidence trail only, no auto-promotion)
```
Status: PROVEN for screener top list and analysis runs. Gap: angles use regular-session bars, no per-session regime tag yet.

## D3. Strategy writing, research and retry
Answers: how a strategy is written (AI, ready-made, user), who decides PASS, what happens on failure.
Vision: A10, A11, B2 (#1, #2), B5 (#1 to #4), B11, D3.3 to D3.5. Decisions 2026-10-07: code decides PASS, one strategy tested on all bar sizes, 30 trades, 3 attempts.

```mermaid
sequenceDiagram
    autonumber
    participant PL as planner
    participant TM as research team (idea generator, writer, backtest runner)
    participant GW as llm-gateway 8099
    participant RS as research-api
    participant SM as simulator (quant-core 8084)
    participant ST as stock-api
    PL->>TM: task for one ticker (write, test SEPARATELY on each bar size, think about the hours)
    TM->>GW: ask for strategy ideas (prompt carries evidence, graveyard, reflection hint)
    GW-->>TM: ideas or error
    Note over TM: sources of a strategy: AI written, ready-made recipe, or user added
    TM->>RS: validate-code (strategy code, symbol, dates)
    loop each bar size, each session set (regular, all)
        RS->>RS: data check (enough bars, complete)
        RS->>SM: simulate custom (code, interval, session)
        SM->>ST: bars for that interval and session
        SM-->>RS: metrics, trades, equity curve
        RS->>RS: deflated Sharpe, holdout, stress test, PBO (waiver stored), 30 trades, per-session breakdown
    end
    RS-->>TM: PASS or FAIL decided by CODE, with reasons and per-bar evidence
    alt FAIL and attempts below 3
        TM->>GW: rewrite using the failure reasons
    else PASS
        TM->>RS: save artifact with bar_interval, bar_evidence, trading_sessions
    end
```
Status: PROVEN that validate-code gives correct values on a real ticker (AMD, all bar sizes) and honestly rejects. TESTED that a pass is possible (planted-edge chain). No real strategy has passed yet. Gap: a deploy kills a running research run. Simulator session-hash fix pending verification.

## D4. Promotion and the fate keeper (gatekeeper, then allocator)
Answers: how a passed strategy becomes ACTIVE, who limits it, how much capital and which sessions.
Vision: A6, A7, A11, A12, A18, B8 (#22, #23), B9 (maturity).

```mermaid
sequenceDiagram
    autonumber
    participant RS as research-api
    participant PF as portfolio-api 8090
    participant RK as risk gatekeeper
    participant MT as maturity assessor
    participant LV as live-api 8091
    RS->>RS: promotion bar re-check from stored evidence (30 trades, PBO or waiver, session match)
    RS->>RS: artifact status becomes ACTIVE (or stays, with the reason)
    PF->>RS: GET artifacts status ACTIVE (in-process first, HTTP fallback)
    PF->>RK: risk checks (correlation, concentration, drawdown, breakers)
    RK-->>PF: allowed or refused with reason
    PF->>MT: maturity tier (opt-in)
    MT-->>PF: capital multiplier
    PF->>PF: allocate risk-parity weights, tilt by deflated Sharpe, halve or flat on drawdown
    PF->>PF: record the funded and the not-funded with reasons
    LV->>PF: GET state, and GET daily-allocation (the second only if scheduler_use_daily_allocation is on, default off)
    PF-->>LV: target weights, deployable equity
```
Status: TESTED on the synthetic chain only. UNPROVEN on a real strategy (there are 0 real ACTIVE strategies). Gaps: the allocation does not carry approved sessions or size multipliers (the order guard reads them from the strategy store itself, see D5). Daily allocation is default off.

## D5. Order flow (target to broker, with every guard)
Answers: who can stop an order, in what order, and what the order looks like at the broker.
Vision: A6 (kill switch), A7, A8, A18, D2 and D3.7.

```mermaid
sequenceDiagram
    autonumber
    participant LV as live scheduler
    participant BR as breaker (daily loss, VaR, leverage, positions)
    participant AG as agent order guard
    participant SS as strategy store (via research)
    participant PF as portfolio-api
    participant AP as Alpaca paper
    LV->>LV: target weights, plus approved live-decision EXECUTE verdicts
    LV->>BR: check limits before orders
    BR-->>LV: ok or halt
    LV->>AG: POST /agent/broker/order (symbol, qty, order type, strategy)
    AG->>AG: kill switch flag and mandate (limits, allowed_sessions)
    AG->>AP: clock, asset (overnight_tradable)
    AG->>AG: session from the broker clock, outside regular only LIMIT with extended_hours
    AG->>SS: strategy ACTIVE, approved for this session (fails CLOSED if unreadable)
    AG->>PF: risk status and state (halt, tier, correlation)
    AG->>AG: size x session multiplier
    alt any check fails
        AG-->>LV: refused with guard code, logged to safety ledger
    else all pass
        AG->>AP: submit order (client_order_id)
        AP-->>AG: id, status pending_new, then new or accepted
        AG-->>LV: submitted
        LV->>AG: GET order by id (poll to filled or canceled)
        AG->>AP: order status and fill
    end
```
Status: the Alpaca side is PROVEN by a real 1-share SPY overnight round trip (placed directly through the broker connection, reconciled). The guard chain is TESTED in code only. UNPROVEN: a real order through live-api and the guard. Gaps: the scheduler does not write its own positions into the book the breaker checks (manifest entry `book.writes->live.scheduler`, status gap). Several guards are default off: entry guards (cooldown, turbulence, data freshness), exits exempt from halts, precondition enforcing.

## D6. The live decision loop (24 hours)
Answers: how a live signal is noticed, judged and handed to execution at any hour.
Vision: A3, A4, A5, A9, A10, B12 (9 points).

```mermaid
sequenceDiagram
    autonumber
    participant PO as live poller (candle close)
    participant ST as stock-api
    participant RS as research-api
    participant TK as stage tracker
    participant DA as deciding agent (agent-api)
    participant GW as llm-gateway
    participant SC as live scheduler
    PO->>RS: GET strategy validations (only research-passed strategies may open positions)
    PO->>ST: latest bars (watermark on the real last bar, not the clock)
    PO->>PO: live indicators, move detection, novelty (observe only)
    PO->>TK: update stage (must_not fired, awaiting confirmation, ready to execute)
    TK-->>PO: freshly ready_to_execute
    PO->>DA: run live decision (context: stage, snapshot, precondition, evidence, past decisions, maturity, reflection notes)
    DA->>GW: judge, with thesis and invalidation
    GW-->>DA: EXECUTE, WAIT or SKIP, with reason
    DA-->>PO: decision, stored append-only
    SC->>PO: unapplied EXECUTE decisions, sized by live_decision_position_size
    Note over SC: an EXECUTE with size 0 is listed at needs-sizing, never traded
    PO->>PO: every N bars review open positions: HOLD or EXIT, plus stop rules and max-hold
```
Status: TESTED only. UNPROVEN on a real strategy. Gaps: REDUCE and ADD are not built. The bar delay for the overnight session is 15 minutes. Precondition enforcing is default off.

## D7. Feedback and learning
Answers: how real results change the next strategies.
Vision: A12, A15, A16, B9, B10, D3.8.

```mermaid
sequenceDiagram
    autonumber
    participant AG as agent (broker link)
    participant LV as live-api
    participant RS as research-api
    participant RF as reflection-worker
    participant HL as hindsight-llm 8092
    participant PL as planner and idea generator
    LV->>AG: reconcile (positions, fills)
    AG-->>LV: broker truth
    LV->>LV: drift between target and actual, alert after 3 cycles
    LV->>AG: append performance (paper return) per strategy
    LV->>RS: shadow evaluate, evaluation history
    RS->>RS: decay check, cut or retire on degradation
    RF->>RS: read outcomes, attribute losses, calibrate thresholds
    RF->>HL: build synthesis (6 analyst clusters)
    PL->>RF: GET synthesis latest (advisory, optional)
    RF-->>PL: synthesis or nothing
    PL->>RS: evaluation status and graveyard feed the next idea prompt
```
Status: UNPROVEN end to end (nothing live to learn from yet). Gaps: the agent's reflection tool points at an address with no HTTP port. Fills are not yet recorded per session. Spread and liquidity per session are not measured.

## D8. The language model door, kill switch and restart
Answers: what happens when the model is down, how everything is stopped, what a restart loses.
Vision: A5 (no-trade is a decision), A6 (kill switch), A17, B9.

```mermaid
sequenceDiagram
    autonumber
    participant AGT as any AI caller
    participant GW as llm-gateway
    participant LM as local or external model
    participant OP as operator
    participant AG as agent-api
    participant LV as live-api
    AGT->>GW: chat completion
    GW->>LM: queued call, one at a time per model
    alt model fails or times out
        LM-->>GW: error
        GW-->>AGT: clear error (caller must not read it as a "no")
        Note over AGT: planner and research record the failure and retry later, no order is ever placed on an AI failure
    else ok
        LM-->>GW: answer
        GW-->>AGT: answer, call kept in history
    end
    OP->>AG: POST /agent/broker/halt (kill switch)
    AG->>AG: halt flag set, every later order refused
    LV->>AG: GET status (halt reason) each cycle and slice
    LV->>LV: block new entries (exits stay allowed)
    OP->>LV: POST emergency flatten
    Note over AG,LV: on restart: stored runs, strategies, orders and evidence are read from disk. A research run in flight is lost (deploy kills it).
```
Status: kill switch and halt TESTED, the gateway history PROVEN in use. Gap: no written rule for a gateway outage of hours. A deploy kills an in-flight research run.

---

## Coverage matrix: vision case to diagram

| Vision case | Diagram | Notes |
|---|---|---|
| A1 pre-trade intelligence, 30 angles | D2 | regime per session missing |
| A2 AI brain, hard risk layer, AI never touches broker | D3, D5 | the order guard sits between |
| A3 structured decision (why) | D6 | decision record with reason |
| A4 expected value | D3, D6 | metrics in D3, judgement in D6 |
| A5 right to say "I don't know" | D6, D8 | WAIT, SKIP, and no order on AI failure |
| A6 risk engine above the AI, kill switch | D4, D5, D8 | |
| A7 dynamic sizing | D4, D5 | portfolio sizing, session multiplier at the guard |
| A8 execution intelligence | D5 | slicing exists in live, not shown |
| A9 re-evaluation, thesis invalidation, time stop | D6 | review every N bars, stop rules |
| A10 bull vs bear vs risk | D3, D6 | committee is opt-in, async |
| A11 backtest is not enough (walk-forward, paper, scaling) | D3, D4 | walk-forward in D3, maturity scaling in D4 |
| A12 degradation detection | D7 | |
| A13 market memory (analogues) | D2, D6 | trend lifecycle rows feed the decision context |
| A14 alternative data | D1 | only search trends, rest deferred |
| A15 audit trail | D5, D7 | safety ledger, decision records |
| A16 post-trade learning | D7 | |
| A17 architecture and metrics | D1 to D8 | whole chain |
| A18 senior-trader rules (WAIT first, funnel, netting, kill switch) | D2, D4, D5, D6 | funnel D2, netting D4 |
| B1 layer map | D1, D2, D4 | |
| B2 items 1 to 10 (evidence, regime tag, pooling, news confound) | D2, D3, D6 | |
| B3 items 11 to 13 (tools, research, simulator audits) | D3 | simulator sandbox in D3 |
| B4 items 14 to 15 (sizing, backfill) | D1, D4 | |
| B5 item 16 (autonomy gaps) | D2, D3 | |
| B6 items 17 to 20 (seams, screener, data, indicators) | D1, D2 | |
| B7 item 21 (cross-cutting patterns) | D1, D3 | point-in-time D1, rejection log D2 and D4 |
| B8 items 22 to 24 (strategy, portfolio, live) | D4, D5 | |
| B9 item 25 (maturity, reflection brain) | D4, D6, D7 | |
| B10 item 26 (seams built) | D5, D6 | |
| B11 strategy schema (8 fields) | D3 | stored on the artifact |
| B12 live-decision 9 points | D6 | |
| B13 deferred items | not drawn | by design: nothing happens |
| D 24-hour system | D1, D3, D4, D5, D6 | sessions in data, test, approval, guard |

Not covered by any diagram (to add if the owner wants them): the user adding a strategy by hand (ready-made and user-added sources appear only as a note in D3), the UI (read-only), and the news-driven path (news only appears as an optional input).
