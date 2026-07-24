# Advanced Vision: Beyond the 4-Stage Gate

See [00-vision-summary.md](00-vision-summary.md) for the base pipeline and
[01-plan-overview.md](01-plan-overview.md) for the base roadmap. This document is an addendum:
what would make the pipeline actually trustworthy for real capital, not just internally
consistent. The base plan (Phases 1–6) gets you a strategy that has been validated once,
refined, compared against alternatives, and documented. That is necessary but not sufficient —
it is still a **static, one-time** judgment. The gaps below are what separates "we ran a
rigorous-looking process" from "we know this makes money and we'll know when it stops."

None of these phases are approved to start. They are documented so the team has the full
picture and can pull individual pieces forward if they're cheap relative to their value (some
are — see priority notes below).

## Why these matter, in priority order

1. **Family-wise overfitting control** (Phase 7a) — cheap, high value, should probably be
   folded into Phase 1/4 rather than treated as separate work. The existing deflated-Sharpe
   correction in `comparison.py` only accounts for candidates tried *within one run*. If a
   ticker has been researched 50 times over a year, the real multiple-testing correction needs
   the lifetime trial count for that ticker, or Stage 0/1 will keep passing strategies that are
   statistically expected to appear by chance alone.

2. **Parameter-surface robustness** (Phase 7b) — probably the single highest-value addition for
   not losing money live. A strategy that passes at one exact parameter point but fails at a
   small perturbation is a knife-edge overfit that Stage 0's Monte Carlo (which only resamples
   trades from the one tested point) cannot catch.

3. **Portfolio-level correlation gate** (Phase 8) — a strategy can be excellent standalone and
   worthless added to the book if it's highly correlated with strategies already running.
   Diversification benefit, not standalone Sharpe, is what actually matters for portfolio risk.

4. **Shadow/paper validation + continuous re-validation ("Stage 4")** (Phase 9) — the biggest
   structural gap. The base pipeline ends at a static playbook document. Real trading needs a
   live feedback loop: paper-trade before real capital, compare realized behavior to what the
   backtest predicted, and keep re-checking a promoted strategy on a rolling basis to catch
   alpha decay — not validate once and forget.

5. **LLM judgment quality control + cost realism** (Phase 10) — Stages 1–3 lean heavily on LLM
   verdicts. Nothing tracks whether those verdicts actually predict live success, or whether
   validation numbers are net of realistic trading costs rather than gross.

## Relationship to the base roadmap

```
Phase 1 (MC foundation) ──┬─▶ Phase 7a (family-wise overfitting) [amends Phase 1/4 storage]
                           └─▶ Phase 10b (cost realism)          [amends Phase 1 validation]

Phase 2 (gate enforcement) ─▶ Phase 7b (parameter-surface robustness) [new stage after Stage 1 PASS]

Phase 4 (comparative critique) ─▶ Phase 8 (portfolio correlation gate) [new precondition on promotion]
                                └─▶ Phase 10a (critic calibration tracking)

Phase 5 (playbook) ─────────────▶ Phase 9 (shadow/live validation)  ["Stage 4" — the loop the playbook currently doesn't close]
```

Phase 7a and 10b are cheap enough that they could realistically be pulled into Phase 1/4's
original scope rather than shipped as separate phases — flag this for discussion when Phase 1
implementation actually starts.
