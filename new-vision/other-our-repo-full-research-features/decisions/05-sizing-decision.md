# Decision — Row 5 Position Sizing (go-live choice 2026-09-07)

> Closes `pending-items-to-be-implemented.md` Row 5 (was provisional `04:400-403`). Decided deliberate, not placeholder.

## Decision

- **risk_gatekeeper approved_size:** `fractional_kelly` quarter-Kelly `vinu-agent/agent/position_sizing.py:52-80` `full_kelly_fraction = (p*b - q)/b` clamped ≥0, then `* kelly_fraction 0.25`. Inputs: `win_rate`, `payoff_ratio = avg_win/avg_loss` from backtest metrics, `account_equity`. Zero edge → 0 size. Env `VINU_AGENT_POSITION_SIZING_METHOD=fractional_kelly` (default `config.py:106`), `VINU_AGENT_KELLY_FRACTION=0.25`, `VINU_AGENT_RISK_PER_TRADE_PCT=0.02`.
- **Fallbacks:** `fixed_fractional` (`capital * 0.02` — 1-2% rule) and `atr_stop` (`(equity*0.02)/(atr*2) * entry_price`, falls back to fixed_fractional if `entry_price/atr ≤0`) `position_sizing.py:83-112`.
- **Portfolio weighting:** `risk_parity` inverse-vol `vinu-portfolio/service.py:210 allocate_risk_parity` → `regime tilt` `service.py:424` + `outcome confidence tilt` `service.py:436` (regime `tilt_bound`, outcome `accuracy`) → `apply_position_sizing` `sizing.py:32` vol-target 15% `vol_targeting_position_size` capped at 1× leverage.

## Why this combo (vs alternatives)

- **Kelly vs HRP vs ATR:** Kelly scales with backtested edge (good for single-candidate approval), HRP needs covariance across book (portfolio layer already does it), ATR needs reliable ATR+entry (not always). Quarter-Kelly is industry conservative (25-50% per `02-reference-repos-core-logic.md`), protects vs Kelly's deep drawdowns (`quantmemo` fractional Kelly).
- **Portfolio HRP+tilt** stays risk-parity with bounded tilts (not LLM-sized) — traceable per `05` PyPortfolioOpt is future enhancement (L2_reg), not blocker.

## Evidence

- `vinu-agent/config.py:95-109` position_sizing knobs env-configurable.
- `vinu-portfolio/service.py:210-289` allocate_risk_parity + `compute_daily_allocation` tilts.
- Existing tests: `vinu-agent/tests/test_position_sizing.py` (if present) + `vinu-portfolio/tests/test_service.py`.

## What remains

- Row 5 now `decided` — enhancement backlog `02-adoptable 05` PyPortfolioOpt HRP/L2 can still be swapped later as optimization, not required for go-live gate.

## Dated

- 2026-09-07 — decided, not provisional. Treat any future placeholder claim as stale.
