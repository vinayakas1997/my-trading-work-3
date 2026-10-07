# pnl_attribution — PnL Attribution

**Cluster:** G — Validation & attribution

## Purpose (verbatim from `angles.yaml`)

Realized-trade PnL statistics per symbol — win rate, average win/loss,
trade count — computed from Phase 6 (vinu-live) execution logs. Every
field includes sample size and confidence interval. Deviates from the
standard runner-driven angle pattern: its natural input is closed
positions/fills, not price bars, so it is push-fed via
`POST /pnl-attribution/{symbol}/record` (Phase 7's feedback loop) rather
than pulled by `AngleRunner` from bars/news.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `closed_positions: list[dict]` (note:
  different input shape from most other angles — real closed
  positions/fills, not a `from_ts`/`to_ts` window)
- **Output (`angle_data`, dict):** PnL attribution results with
  confidence intervals.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "win_rate": 0.58,
      "win_rate_ci": [0.49, 0.67],
      "avg_win_pct": 0.021,
      "avg_loss_pct": -0.014,
      "trade_count": 19
    }
  ]
}
```

## Condensed glossary blurb (draft)

*This system's OWN real, closed-trade track record for this symbol —
not a general backtest like `backtesting_44_metrics`, this is what
actually happened on real fills. Low `trade_count` means a wide,
unreliable confidence interval; check it before trusting the win rate.*
(~40 words)
