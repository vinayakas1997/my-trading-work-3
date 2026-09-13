# research-discussion-v2 — full pipeline audit (2026-09-12)

This folder documents a second, deeper audit pass over `vinu-components`, requested
after the earlier efficiency-focused audit (see `../research-discussion-v1/`) had
already been fixed, committed, and pushed.

## Scope and method

Where v1 asked "is anything wasteful/duplicated," this pass asked a different
question: **trace every real pipeline end-to-end, from its actual entry point to
its final effect, and find where the negative/failure path is missing, wrong, or
fails in the unsafe direction.** Four pipelines were audited in parallel by
independent agents, each required to cite exact `file:line` and a concrete
input/condition -> outcome, not style opinions:

1. **Market data ingestion** — vinu-stock-price, vinu-news, vinu-screener
2. **Research & backtest** — vinu-research, vinu-simulator, vinu-strategy
3. **Live agent decision & execution** — vinu-agent (LLM loop, tools, order_guard) + vinu-live
4. **Portfolio & risk state** — vinu-portfolio, vinu-infra, and their callers

## Files in this folder

- [`findings.md`](findings.md) — the full findings list as reported by the four audits, organized by severity, before any fix was made. This is the frozen record of what was found.
- [`fixes-log.md`](fixes-log.md) — updated incrementally as each finding is fixed: what changed, why, how it was verified, and any finding that was deliberately *not* changed (with the reasoning).

## Status

Audit complete. Every finding is now either fixed and independently verified,
or reviewed with documented reasoning for why it was deliberately left
unchanged (existing, explicit, tested fail-open design decisions in
`order_guard.py`, not oversights). This includes the two items that initially
looked like they needed a bigger architecture change (symbol grounding,
pre-execution trade auditing) — both got a properly scoped real fix once
traced through the actual tool-calling plumbing rather than being left open.
See `fixes-log.md` for the full breakdown.
