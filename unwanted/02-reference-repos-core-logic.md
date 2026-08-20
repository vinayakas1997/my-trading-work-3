---
name: reference-repos-core-logic
status: findings from direct exploration of the two reference repos (2026-08-17)
purpose: what's genuinely mature and worth porting into vinu-components from Jarvis and jarvis-trading-bot, versus what's present but not worth adopting. Grounded in actual file paths read during the exploration, not general impressions.
---

# Core logic worth taking from the reference repos

Source repos:
- `/home/somic_cps/Vina/my-trading-work-3/personal-important/other-reference-repos/Jarvis`
- `/home/somic_cps/Vina/my-trading-work-3/personal-important/other-reference-repos/jarvis-trading-bot`

## Worth porting

### 1. Position sizing for `risk_gatekeeper` — Kelly is one option among several

Directly closes shortcoming #7 in the companion file: `risk_gatekeeper`
today has no sizing formula, only a fit check. `jarvis-trading-bot/risk_manager.py`
has real Kelly-criterion sizing and ATR-based dynamic sizing, plus
max-drawdown/circuit-breaker constants — confirmed the one
professionally-written file in an otherwise duplicated, `_old`/`_v2`–`_v9`-
littered codebase, math sound even though the surrounding app isn't. But
Kelly is not the only standard approach, and each has real tradeoffs worth
weighing rather than defaulting to the one this repo happens to have:

- **Kelly Criterion (full or fractional).** Maximizes long-run geometric
  growth given a win-rate/payoff-ratio estimate. Full Kelly is famously
  aggressive — small errors in the edge estimate cause large oversizing, so
  it's almost always run as **fractional Kelly** (25-50% of suggested size)
  in practice. Needs a trustworthy edge estimate — which is exactly what
  the sweep + PBO + (proposed) walk-forward chain in Researcher/Executor is
  trying to produce, so this is a good fit *if* those upstream numbers are
  trusted, weaker if not.
- **Fixed Fractional (the "1-2% rule").** Risk a fixed % of account equity
  per trade, position size derived from stop-loss distance. What Jarvis's
  `core/risk_manager.py` actually implements. Simple, doesn't depend on an
  edge estimate at all, self-corrects as account size changes. Doesn't scale
  size with conviction — a high- and low-confidence trade with the same stop
  distance get sized identically.
- **ATR-based / volatility-scaled sizing.** Size inversely proportional to
  recent volatility so every position carries roughly equal dollar-risk
  regardless of instrument volatility. What jarvis-trading-bot layers on top
  of Kelly — volatility-normalizes the position, doesn't replace the "how
  much edge do I have" question. Complementary to Kelly/fixed-fractional,
  not a competitor.
- **Volatility/Risk Parity across the portfolio.** Allocate so each open
  position contributes equal *risk* to the total portfolio rather than equal
  capital. `capital_allocator` already does a portfolio-level version of
  this (ranking by deflated Sharpe, batch correlation checks) — this would
  sit one layer below it, at `risk_gatekeeper`, for per-trade sizing.
- **Optimal f / CPPI.** Less common in practice — optimal f is a Kelly
  variant tuned off historical trade sequences rather than a win-rate
  estimate; CPPI is more an insurance/floor-protection technique than a
  sizing method. Noted for completeness, not recommended — both are more
  fragile to regime change than the above three.

**Recommendation, not a decision made for you:** fractional Kelly (25-50%)
sized off the sweep's own PASS-verdict confidence, then ATR-normalized so
dollar-risk stays volatility-consistent across tickers — this uses the
conviction signal the pipeline already computes, rather than throwing it
away. Fixed-fractional alone is the safer starting point if Kelly isn't
trusted yet against real sweep output. This is a judgment call on how much
to trust the edge estimates right now, not something to lock in without
watching it run first.

**How to use it:** port the sizing functions themselves into a helper
`risk_gatekeeper` calls before approving a candidate. Do not import the
surrounding Telegram/broker app — just the calculation.

### 2. Walk-forward validation — `Jarvis/core/backtesting/walk_forward.py` + `monte_carlo.py`

Directly closes shortcoming #8: your sweep already has PBO
(`vinu-research/vinu_research/pbo.py`), but nothing tests parameter
stability across rolling time windows. This is real backtesting-engine code
from an actively deployed system (`core/backtesting/` also has
`backtest_engine.py`, `parameter_optimizer.py`), not a stub.

**How to use it:** add as a second gate inside Researcher/Executor's role c
self-verdict, alongside the existing PBO check — complementary, not
redundant.

### 3. LLM provider waterfall — `jarvis-trading-bot`'s `_call_llm()`

Groq → Gemini → OpenRouter fallback chain, in `jarvis_agents.py`. Simple and
resilient. Worth adopting if the Planner or Researcher/Executor currently
have no fallback and a single provider outage would stall the pipeline
(see shortcoming #9 — unconfirmed, check first).

## Present but not mature enough to port

- **Jarvis's Planner→Executor→Observer→Reflector agent graph +
  `AgentRegistry`** (`core/agent_graph.py`, `core/agents/registry.py`) —
  routes tasks by capability tag and tracks per-role success rate. An
  interesting idea (route by historical accuracy) but the mechanism itself
  is bespoke and less disciplined than what's already built here — no
  fail-closed completeness thresholds, no shared K-cap counters, no
  single-authority-over-close design. Not worth adopting the mechanism.
  The underlying idea — track success rate per role, let the Planner use it
  when choosing between recipe-based and raw-code-generation paths — is a
  future refinement worth remembering, not a near-term port.
- **Jarvis's Solana sniping engine / `services/investments/` DeFi
  orchestrator** — real, production-grade code, but for a different asset
  class and execution style (on-chain DEX sniping) than this pipeline
  targets. No direct reuse.
- **jarvis-trading-bot's per-user flat-JSON memory store**
  (`memory_store/user_<chat_id>.json`) — a reasonable minimal design for a
  single-user consumer bot, but `HypothesisRegistry`/`TickerLedger` here are
  already more structured and closed-loop. Adopting this would be a
  downgrade.
- **jarvis-trading-bot's "multi-agent" specialist routing**
  (`jarvis_agents.py`'s `route_to_specialist()`) — regex-keyword routing to
  system-prompt strings, single LLM calls, no tool-calling, no planner/
  executor loop. Explicitly not worth learning from — the existing Planner/
  Researcher-Executor design here is categorically more sophisticated.

## Recommendation, ranked

1. Port Kelly/ATR sizing math into `risk_gatekeeper` (closes shortcoming #7).
2. Add walk-forward next to PBO in Researcher/Executor's role c (closes
   shortcoming #8).
3. Add an LLM provider fallback if none exists today (closes shortcoming #9,
   pending confirmation it's actually missing).

Everything else in both repos is either a different problem domain or
architecturally behind what's already built and wired in vinu-components —
not worth the incorporation cost.
