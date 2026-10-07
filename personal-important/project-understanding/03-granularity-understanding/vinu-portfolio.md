# vinu-portfolio

## What it is

The cross-strategy allocation and drawdown-protection layer — computes
how much weight each active strategy should get (correlation-aware, not
just per-strategy), and independently watches whole-portfolio drawdown to
trigger the real kill switch if it breaches.

## Trigger / cadence

Two independent processes plus several one-shot CLI commands (`cli.py`):

1. **Drawdown monitor** (`vinu-portfolio monitor`,
   `drawdown_scheduler.py::monitor_main_loop`) — a `while True` loop,
   default **300 seconds (5 min)** (`drawdown_monitor_interval_sec`).
2. **HTTP API** (`vinu-portfolio serve`) — always up, answers on-demand
   allocation builds.
3. One-shot commands, not scheduled by this service itself (an operator
   or another process' scheduler triggers them): `build` (print weights),
   `daily-allocation`, `daily-game-plan`, `risk-status`,
   `historical-simulate`.

## Pipeline

**`build_portfolio()`** (`service.py`, the actual allocation pipeline,
per its own docstring — 4 stages, in order):
1. **List active strategies** — YAML-configured strategies + LLM-sourced
   ones (`vinu-research` artifacts, via `research_link.py`, in-process,
   not an HTTP call). Optionally includes `extra_candidates` — PEND
   artifacts from `vinu-agent`'s capital_allocator batch, evaluated
   *alongside* the real ACTIVE book in the same pass, `is_candidate=True` —
   this is how a not-yet-funded candidate's would-be weight and
   correlation with the existing book gets computed without it needing to
   already be ACTIVE.
2. **Compute correlation matrix** (`risk_utils.py`) — Ledoit-Wolf
   shrinkage first, then unconditional spectral PSD repair (fixed this
   project's own default: correctly no longer produces exact ±1.0 from
   tiny synthetic series).
3. **Risk-parity allocation** — `allocation_mode` default is **`hrp`**
   (Hierarchical Risk Parity — clustering + recursive bisection, no
   covariance inversion), falling back to `inverse_vol` automatically on
   short history. Both a default flip made deliberately during this
   project's own Stage-C work, not the library's original default.
4. **Apply constraints** — `cap_concentration()` (a per-strategy cap
   applied *after* renormalization, since applying it before would
   silently undo itself), `rescale_correlated_clusters()` (post-construction
   cap on a correlated block's *combined* weight, default
   `max_correlated_cluster_weight=0.6`, opt-in threshold via
   `cluster_corr_threshold`).

**Drawdown monitor cycle** (every 5 min, `circuit_breakers.py::PortfolioDrawdownMonitor.check`):
1. Fetch current portfolio value (`vinu-agent`'s `/agent/broker/account`).
2. Two independent breach checks: **drawdown-from-peak** (de-risk
   schedule: halve exposure at -10%, flat at -15%, halt at -20% — the
   code's own comment) and **absolute session loss** (opt-in,
   `VINU_PORTFOLIO_ABS_LOSS_HALT` — a straight loss-from-session-start
   threshold, independent of the peak-relative one; either alone can
   trigger the halt).
3. On breach: `_halt_trading()` — calls the REAL global kill switch via
   `vinu-agent`'s `/agent/broker/halt` (the same filesystem-backed switch
   `OrderGuard.check()` reads and scenario 07 verified against directly),
   not a local-only flag.

## Storage

None of its own beyond config/YAML — reads strategies live from
`vinu-research` (in-process `research_link.py`) and price/broker state
over HTTP each build/check.

## Talks to

- **Outbound**: `vinu-agent` (`/agent/broker/account` for equity,
  `/agent/broker/halt` on a drawdown breach — this is one of the real
  external triggers for the kill switch scenario 07 verified, alongside
  a manual `/agent/broker/halt` call and an emergency-flatten), price
  data for correlation computation, `vinu-research`'s strategy store
  in-process.
- **Inbound**: `vinu-agent`'s capital_allocator hands PEND candidates
  here via `extra_candidates` to price their would-be portfolio impact
  before funding them.
