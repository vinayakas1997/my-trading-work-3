# backtesting_44_metrics — Backtesting Metrics

**Cluster:** G — Validation & attribution

## Purpose (verbatim from `angles.yaml`)

Compute 44+ portfolio metrics — Sharpe, Sortino, MaxDD, WinRate, CAGR,
VaR, CVaR, tail ratio.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D, 1W, 1M, 6M
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** "Angle-specific results" (catalog
  gives no field-level schema here — the fake example below is built
  from the `purpose` field's real metric list instead).

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "sharpe": 1.15,
      "sortino": 1.62,
      "max_drawdown_pct": -0.18,
      "win_rate": 0.54,
      "cagr": 0.12,
      "var_95": -0.021,
      "cvar_95": -0.034,
      "tail_ratio": 1.08,
      "trade_count": 142
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A backward-looking backtest scorecard (44+ real metrics: Sharpe,
drawdown, win rate, VaR/CVaR) — not a forecast. Tells you how a
strategy/symbol has actually performed historically, useful evidence,
never a signal about what happens next.* (~35 words)
