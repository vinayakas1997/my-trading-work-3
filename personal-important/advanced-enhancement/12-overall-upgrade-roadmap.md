# Overall Upgrade Roadmap: From 8/10 to 10/10

## Executive Summary

This document provides the phased implementation roadmap to take the Vinu trading platform from its current state (approximately 75-80% of a production-grade quant system) to a full 10/10 system. The upgrades are organized into 4 phases spanning approximately 6-8 weeks of development effort for a senior developer or small team.

## Current Scores by Component

| Component | Current Score | Target Score | Gap |
|-----------|--------------|--------------|-----|
| Microservices architecture | 9/10 | 10/10 | Minor: auth, monitoring |
| Backtesting engine | 8/10 | 10/10 | Walk-forward, advanced costs |
| News-price correlation | 8/10 | 9/10 | Real-time correlation |
| Circuit breaker / resilience | 8/10 | 9/10 | Centralized observability |
| Test coverage | 7/10 | 10/10 | Integration tests |
| Documentation | 8/10 | 9/10 | Deployment docs |
| **Strategy generator** | **5/10** | **10/10** | **LLM generation, 20+ templates** |
| **Risk metrics** | **6/10** | **10/10** | **CVaR, VaR, tail risk, turnover** |
| **Benchmark comparison** | **3/10** | **10/10** | **Alpha, beta, IR, capture ratios** |
| **Walk-forward validation** | **4/10** | **10/10** | **OOS testing, IS/OOS gap check** |
| **Regime detection** | **3/10** | **10/10** | **HMM classifier, regime-contingent logic** |
| **Position sizing** | **4/10** | **10/10** | **Kelly, vol-target, signal sizing** |
| **Multi-asset portfolio** | **3/10** | **10/10** | **Universe, correlation, sector limits** |
| **Slippage modeling** | **7/10** | **10/10** | **Volume-based, time-of-day, calibrated** |
| **Paper trading bridge** | **2/10** | **10/10** | **Live deployment, monitoring** |
| **Strategy versioning** | **4/10** | **10/10** | **Registry, A/B testing, audit trail** |
| **Security** | **6/10** | **10/10** | **Sandbox exec, auth, monitoring** |
| **CI/CD** | **1/10** | **10/10** | **GitHub Actions, linting, deployment** |

## Phase 1: Foundation (Weeks 1-2) — Score impact: +0.8

### Focus: Make the research loop scientifically rigorous

| # | Enhancement | Days | Dependencies | Score Impact |
|---|-------------|------|--------------|-------------|
| 1 | **Walk-forward validation** | 5 | None | +2.0 on validation (6→10) |
| 2 | **Extended risk metrics** | 2 | None | +1.5 on metrics (6→9) |
| 3 | **Benchmark comparison** | 2 | None | +3.0 on benchmark (3→9) |

**Why Phase 1 first**: These three enhancements make the existing system's outputs **scientifically valid**. Without walk-forward, all backtest results are suspect. Without benchmark comparison, you can't tell if a strategy is good. Without proper risk metrics, you can't evaluate tail risk.

**Phase 1 Deliverables:**
- `01-walk-forward-validation.md` implemented
- `05-risk-metrics-extended.md` implemented (minus benchmark-dependent parts)
- `07-benchmark-comparison.md` implemented
- Risk critic has 7 new rules covering IS/OOS gap, tail risk, alpha, information ratio

## Phase 2: Intelligence (Weeks 3-4) — Score impact: +1.2

### Focus: Make the strategy generator truly intelligent

| # | Enhancement | Days | Dependencies | Score Impact |
|---|-------------|------|--------------|-------------|
| 4 | **Strategy generator upgrade** | 10 | Phase 1 (for validation) | +2.5 on generator (5→10) |
| 5 | **Regime detection** | 6 | Phase 1 (for metrics) | +2.5 on regime (3→9) |
| 6 | **Position sizing** | 3 | None | +2.5 on sizing (4→9) |

**Why Phase 2 second**: The generator upgrade is the biggest single improvement. With LLM-generated code, the system becomes an actual "researcher" rather than a template filler. Regime detection provides market context for the risk critic. Position sizing ensures good strategies are optimally capitalized.

**Phase 2 Deliverables:**
- `06-strategy-generator-upgrade.md` implemented (20+ templates + LLM mode)
- `02-regime-detection.md` implemented (HMM classifier + regime-contingent logic)
- `03-position-sizing.md` implemented (Kelly, vol-target, signal-strength)
- Strategy count goes from 3 → 20+ templates + unlimited LLM-generated

## Phase 3: Scale (Weeks 5-6) — Score impact: +0.7

### Focus: Move from single-stock to multi-asset, realistic costs

| # | Enhancement | Days | Dependencies | Score Impact |
|---|-------------|------|--------------|-------------|
| 7 | **Multi-asset portfolio** | 10 | Phase 2 (generator) | +2.5 on portfolio (3→9) |
| 8 | **Advanced slippage model** | 4 | Phase 1 (metrics) | +1.0 on slippage (7→9) |

**Why Phase 3 third**: Multi-asset support requires the generator and regime detection from Phase 2 to be fully useful (you need intelligent signal generation per asset). Advanced costs are important but not blocking.

**Phase 3 Deliverables:**
- `04-multi-asset-portfolio.md` implemented
- `08-slippage-market-impact.md` implemented
- Can run research on universes of 10-50 symbols
- Slippage costs are calibrated per symbol

## Phase 4: Production (Weeks 7-8) — Score impact: +0.5

### Focus: Bridge to live trading, operational hardening

| # | Enhancement | Days | Dependencies | Score Impact |
|---|-------------|------|--------------|-------------|
| 9 | **Paper trading bridge** | 12 | Phase 3 (multi-asset) | +3.0 on paper trading (2→9) |
| 10 | **Security & architecture** | 6 | None | +1.5 on security (6→9), +1.0 on CI/CD (1→5) |
| 11 | **Strategy versioning** | 3 | Phase 1 (walk-forward) | +2.0 on versioning (4→8) |

**Why Phase 4 last**: Paper trading requires all the intelligence from Phases 1-3 to be worth deploying. Security and CI/CD are operational concerns. Versioning is valuable but doesn't need to be built first.

**Phase 4 Deliverables:**
- `10-live-paper-trading-bridge.md` implemented (vinu-trader service)
- `09-security-and-architecture.md` implemented (sandboxed exec, auth, monitoring)
- `11-strategy-versioning.md` implemented (registry, A/B testing)
- Full docker-compose with all 8 services + monitoring stack

## Detailed Week-by-Week Plan

```
Week 1: Walk-forward validation (4d) + Extended metrics (1d)
Week 2: Benchmark comparison (1d) + Start generator upgrade (templates, 4d)
Week 3: Generator upgrade (LLM mode, 4d) + Start regime detection (1d)
Week 4: Regime detection (4d) + Position sizing (1d)
Week 5: Multi-asset portfolio — universe + correlation + risk critic (5d)
Week 6: Multi-asset generator + Advanced slippage (5d)
Week 7: Paper trading — executor + broker (5d)
Week 8: Paper trading — monitoring + Security sandbox + Strategy registry (5d)
```

## Effort Summary

| Category | Days | % of Total |
|----------|------|------------|
| Scientific rigor (WF, metrics, benchmark) | 8 | 17% |
| Intelligence (generator, regime, sizing) | 19 | 40% |
| Scale (multi-asset, costs) | 14 | 29% |
| Production (paper trading, security, versioning) | 21 | 44% |
| **Total** | **~48 man-days** | **100%** |

*Note: Overlap possible with a 2-person team — total calendar time ~6 weeks.*

## Risk Matrix

| Enhancement | Risk Level | Key Risk | Mitigation |
|-------------|------------|----------|------------|
| Walk-forward | 🟢 Low | No edge cases for date splitting | Extensive unit tests |
| Extended metrics | 🟢 Low | Numerical edge cases (div by zero) | Tolerate NaNs |
| Benchmark | 🟢 Low | Benchmark data unavailable | Graceful None fallback |
| Generator upgrade | 🟠 Medium | LLM generates bad code | Validation pipeline catches |
| Regime detection | 🟠 Medium | HMM misclassifies regimes | Allow manual override, simple fallback |
| Position sizing | 🟢 Low | Kelly overestimates edge | Fractional Kelly default (0.25) |
| Multi-asset | 🔴 High | Performance with 50+ symbols | Parallel processing, caching |
| Slippage model | 🟢 Low | Calibration requires data | Reasonable defaults per tier |
| Paper trading | 🔴 High | Broker API failures | Circuit breaker, manual fallback |
| Security | 🟠 Medium | Sandbox bypass | AST analysis + restricted globals |
| Strategy versioning | 🟢 Low | Database corruption | SQLite WAL mode, backups |

## Expected Score After Each Phase

```
Phase 0 (Current):    7.2/10
Phase 1 (Scientist):  8.0/10  (+0.8)
Phase 2 (Intelligent): 9.2/10 (+1.2)
Phase 3 (Scaled):     9.9/10 (+0.7)
Phase 4 (Production): 10.0/10 (+0.1 but critical for ops)
```

## Technology Stack Summary

| Purpose | Change | Packages/Libraries |
|---------|--------|--------------------|
| HMM regime classifier | NEW | `hmmlearn` (or build with NumPy) |
| Walk-forward | NEW | None (pure Python) |
| LLM code generation | MODIFY | Existing `httpx`, Astor for code formatting |
| Prometheus metrics | NEW | `prometheus-client` |
| Paper trading | NEW | `alpaca-py` (Alpaca Trading API) |
| Structured logging | NEW | `python-json-logger` or custom |
| Shared deps | NEW | `uv` workspace |

## Decision Points

Before starting each phase, these decisions need to be made:

1. **Phase 1**: What's the default walk-forward configuration? (3 windows? 5 windows? Sliding or expanding?)
2. **Phase 2**: Should LLM-generated code be the default or opt-in? (Safety vs creativity trade-off)
3. **Phase 3**: What universe size should the system target? (10 symbols MVP? 100 symbols for real use?)
4. **Phase 4**: Which broker for paper trading? (Alpaca is simplest, Interactive Brokers for professional use)

## Final Recommendation

1. **Start with Phase 1** — It's the lowest effort (8 days) and highest scientific impact. Every backtest result produced today is potentially misleading without walk-forward and benchmark comparison.

2. **Prioritize Phase 2 over Phase 3** — The generator upgrade (+2.5 score impact) and regime detection (+2.5) are higher value than multi-asset (+2.5 but much more effort). A system that generates intelligent single-stock strategies is better than one that generates dumb multi-asset strategies.

3. **Phase 4 should be continuous** — Security hardening (sandboxed exec) should be done early, not last. The `exec()` vulnerability is a real risk even in backtest-only mode.
