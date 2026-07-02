# Open-Close Return

## Why use it

- Isolate **intraday** session performance (open to close), stripping overnight gap effect.
- Separate "gap" from "trade" — did the stock rally after the open or sell off intraday?
- Useful for day-trader mindset on daily bars and gap-fill analysis.

## What it is

- **Open-to-close return** — `(close − open) / open` for each bar.
- Positive = bullish session (closed above open); negative = bearish session.
- **Inputs:** `open`, `close` | **Outputs:** `open_close_return` | **Warmup:** 1 bar

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `open_close_return` > 0 | Bullish day session | Buyers controlled the day after the open |
| `open_close_return` < 0 | Bearish day session | Sellers controlled from open to close |
| Large positive OC + negative `daily_return` | Gap down, rallied | Gap-fill / reversal day |
| Large negative OC + positive `daily_return` | Gap up, sold off | "Gap and crap" — distribution |
| Small OC, large daily return | Overnight gap dominated | Focus on gap drivers (news, global cues) |

## How to combine

- **Daily return:** Compare gap vs session — `daily_return` vs `open_close_return` (see `daily_return/README.md`).
- **High-low spread:** Wide spread + negative OC → intraday rejection of highs (see `high_low_spread/README.md`).
- **Volume:** Strong OC move on high `volume_ratio_20` → conviction (see `volume_ratio/README.md`).
- **Recipe:** `full_ta`.

## Caveats

- Open print can be distorted by opening auction mechanics.
- Not a standalone signal — always pair with gap context and trend.
- Daily bars only — not a substitute for true intraday tape.

## Market notes

- **A — Generic daily equities:** Essential for separating overnight risk from session trend.
- **B — India (NSE/BSE):** Pre-open session (9:00–9:15) sets open; global cues often create gap vs OC divergence.
- **C — US equities:** Earnings released pre-market create classic gap-up/down + OC fade patterns.

## In this codebase

- Path: `indicators/open_close_return/open_close_return.py`
- Feature name: `open_close_return`
- Also included in: `full_ta`
