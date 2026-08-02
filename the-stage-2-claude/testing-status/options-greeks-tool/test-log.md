# options-greeks-tool — Test Log

**Status:** Not started.

## What will be tested / Expected output

- Direct tool call (bypassing the LLM loop) against a real, liquid,
  optionable symbol (AAPL) during market hours — confirm the response
  contains non-null Greeks (delta, gamma, theta, vega, rho) and implied
  volatility for at least a few near-the-money contracts.
- Confirm a clean, honest error (not a crash) for a symbol with no listed
  options, or outside market hours if the endpoint requires it.
- End-to-end: confirm the LLM actually invokes the tool via a real
  `vinu-agent` chat session given a natural prompt (e.g. "what's the
  implied volatility on AAPL right now") — a tool that only works when
  called directly, never invoked by the LLM in practice, is not done.
- Explicitly NOT tested: historical options backfill. This tool is
  present-time only by data-source design (Alpaca's Greeks/IV endpoint
  has no historical lookup) — don't write a test expecting historical
  coverage.
- Full detail: [../../scope-responsibilities/04-options-greeks-tool.md](../../scope-responsibilities/04-options-greeks-tool.md)

## Bug / Fix Log

_Nothing logged yet — testing has not started._
