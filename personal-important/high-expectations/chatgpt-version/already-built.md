# Already built — cross-check against `how-the-system-should-be.md` / `how-he-will-trade.md`

This file tracks, point by point, which of the senior-quant expectations
in this folder's two source docs are already real in the codebase today —
checked directly against the code, not assumed from the docs' own
wording. Where something was found only *partially* built, or genuinely
missing, that's said plainly rather than rounded up.

Cross-referenced in the main audit series at
`missing-pieces-of-system/new-theory-of-trading/system-wide-audit-and-design/`
(`00-overview.md`, item #25; `02-open-questions-strategy-and-simulation.md`,
item #25's dated updates).

## Fully built

- **Pre-trade market understanding** — regime detection, trend
  structure, momentum, news, correlation, and historical-pattern
  signals are all real, computed angles (`vinu-initial-analysis/angles/`:
  `regime_analysis`, `trend_lifecycle`, `news_price_causality`,
  `signal_evidence`, `peer_relative_strength`, and 25+ others).
- **Multi-agent "market brain" + a hard risk layer between AI and
  execution** — separate angles feed a common signal; the AI never
  talks to the broker directly (`risk_gatekeeper`/`order_guard` sit
  between).
- **Structured trade decisions, not a bare signal** —
  `vinu-research/trade_score_calibration.py`'s `TradeScore` carries
  regime fit, expected value, risk, and risk/reward together, not a
  bare confidence number.
- **Expected value over confidence** — `TradeScoreResult`'s `ev_score`
  is a real, scored expected-value component.
- **A deterministic risk engine that can override the AI** —
  `vinu-portfolio/circuit_breakers.py`, `risk_gatekeeper`, `order_guard`
  enforce limits independent of any model's own confidence.
- **Execution intelligence — VWAP/TWAP slicing** —
  `vinu-live/vinu_live/execution.py` plans real volume-weighted and
  time-weighted order slicing, not just market orders.
- **Continuous re-evaluation of open positions / thesis invalidation** —
  the `live_decision` system (`vinu-live/vinu_live/live_decision/`,
  reverse-engineered and built earlier in this same audit thread).
- **Adversarial bull/bear/risk debate** — `vinu-agent`'s
  `investment_committee` swarm preset has real `bull_advocate`,
  `bear_advocate`, `risk_officer` agents. Built, but **opportunistic/
  async, not a mandatory gate on every trade** (`routes_swarm.py`'s own
  docstring: "if nothing has completed yet, callers get 'none' and
  simply proceed") — kept that way on explicit instruction rather than
  made blocking, since that would add real LLM-debate latency to every
  trade.
- **Three-way decisions (BUY/WAIT/SHORT), not two** — real in the
  loop's PASS/REFINE/STOP path and `live_decision`'s HOLD/ADD/REDUCE/
  EXIT states.
- **Selectivity — a real multi-stage funnel** — hard filters → K-cap
  gate (`thesis_intake_gate.py`) → Monte Carlo gate → holdout gate,
  cutting candidate ideas down before any capital is at risk.
- **A formal "Trade Score" checklist, self-calibrating** —
  `trade_score_calibration.py`, more sophisticated than the doc even
  asked for: it nudges its own scoring weights toward whatever
  historically predicted winning trades, not fixed hand-picked weights.
- **A hard risk:reward floor** — `gates/trade_score_gate.py`'s
  `_reward_risk_ratio()` force-sets the tier to `no_trade` below
  `min_reward_risk_ratio` (default 1.5), called live inside
  `trade_plan_authoring.py`'s gate chain. (Earlier check-in wrongly
  called this "partial" — corrected once verified.)
- **Portfolio-level correlation thinking** —
  `vinu-portfolio/shock_correlation.py` (DCC-GARCH/Gerber shock
  correlation) plus symbol-conflict netting; correlated bets get
  flagged/reduced, not each sized as if independent.
- **A hard kill switch** — `circuit_breakers.py`'s `_halt_trading`,
  confirmed wired into the main live-rebalance cycle (this audit
  series' own item #24 fix).
- **Strategy-degradation detection** — `vinu-research/decay.py`
  (`DecayThresholds`, `DecaySnapshot`), the same adaptive machinery
  `trade_score_calibration.py` itself reuses.
- **Market memory / historical analogues** —
  `trend_lifecycle/patterns.py` does real KNN pattern-matching against
  a historical peak/trough library ("N similar historical situations").
- **A full per-trade audit trail** — `trade_audit_log.py` plus run
  cards, already extensive.
- **A post-trade learning loop** — `HypothesisRegistry`'s evidence
  trail, plus a dedicated `vinu-reflection` service doing loss
  attribution and threshold calibration.
- **Evaluated on the right metrics, not win rate** — Sharpe/Sortino/
  max drawdown/expectancy/turnover/VaR/CVaR are all computed already
  (`vinu-simulator/engine/metrics.py`).
- **A unified "why isn't this trading" view** —
  `vinu_infra/strategy_evaluation.py`'s `StrategyEvaluationStore`
  already consolidated every gate's verdict into one current-state
  summary (`get_status`/`get_history`); it just had no HTTP surface.
  New: `GET /research/evaluation-status/{artifact_id}`,
  `GET /research/evaluation-status/by-ticker/{ticker}`,
  `GET /research/evaluation-history/{artifact_id}`.
- **Composite position sizing** — `vinu-simulator/engine/sizing.py`'s
  new `CompositeSizer` multiplies vol-target sizing with
  correlation-aware shrinkage (the DCC-GARCH/Gerber math relocated to
  shared `vinu_tools/compute/risk/shock_correlation.py` so both
  services use the same implementation, not two).
- **Gradual capital scaling** — a system-wide `MaturityAssessment`
  (cold_start/paper_only/early_live/mature) previously only reached an
  LLM prompt. New, opt-in `maturity_capital_gating_enabled` in
  `vinu-portfolio` scales `deployable_equity` by a per-tier multiplier,
  the same whole-portfolio mechanism the drawdown ladder already uses.
  Fails open (full capital) if the assessment is unavailable.
- **Search-trends alternative data** — new `search_trends` angle
  (`vinu-initial-analysis`, the 30th angle), via `pytrends` (no paid
  tier or API key needed): weekly Google search interest with a rolling
  z-score, plus a real forward-return correlation backtest.

## Partially built / real limitations worth naming

- **"I don't know" / uncertainty** — expressed only indirectly, via
  several independent gates (trade-score tier, correlation gate,
  calibration gate) rather than one explicit uncertainty signal. Each
  gate's own verdict is now visible in one place (see
  `StrategyEvaluationStore` above), but there's no single "confidence
  score" abstraction tying them together.
- **Evidence-confidence and drawdown-aware sizing factors** — named in
  the composite-sizing ask alongside vol-target/correlation, but not
  built: evidence-confidence has no sketch anywhere in the codebase
  (confirmed by a fresh grep), and drawdown-aware sizing would need
  real extraction work out of `PortfolioDrawdownMonitor` (a live-polling
  design, not a pure function callable inside a backtest loop) first.
- **Bull/bear/risk debate as a mandatory gate** — real and working, but
  intentionally kept opt-in/async rather than blocking (see above).

## Explicitly deferred, not built

- **Order-book / L2 market depth** — gated behind a paid subscription
  tier on both Alpaca and Polygon; the current API keys' scope doesn't
  include it. Needs a paid-tier decision (and cost) before any code
  change is useful.
- **On-chain crypto data** — the system only trades equities through
  Alpaca paper trading today; nothing anywhere actually holds or
  executes a crypto position, so on-chain ingestion would have zero
  real consumer right now. Deferred until the system actually trades
  crypto, not just in agent-persona prompt text.
- **A "step-8 synthesis agent"** that reads across every reflection
  finding and notices when separate findings are one story — explicitly
  scoped *out* of the current build (per `maturity-agentic-system`'s own
  implementation-status notes), despite the data for it already
  existing and sitting unconsumed.
