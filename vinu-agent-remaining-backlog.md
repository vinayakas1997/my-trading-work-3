---
name: vinu-agent-remaining-backlog
status: reference
purpose: extracted from compare-vinu-vine-project-status/ before that folder was deleted — the still-open items from the Vibe-Trading comparison that hadn't been captured anywhere else. Not a committed plan, just a durable list of what's actually left.
---

# vinu-agent — Remaining Backlog (extracted 2026-08-02)

**Source:** `compare-vinu-vine-project-status/compare-2/01-vinu-vs-vibe-trading-coverage-status.md`
(dated 2026-07-15) and `02-vinu-vs-vibe-trading-gap-analysis.md`, before that
folder was deleted as redundant. The comparison narrative itself (vinu vs.
the external "Vibe-Trading" reference project) was stale and safe to drop —
the current system has grown well past what that doc describes (10 services
now, not 7; `vinu-portfolio`/`vinu-live` didn't exist yet; `vinu-initial-analysis`
had none of the market-model/FinBERT/significance-classifier work this
session added). This file keeps only the concrete unfinished-work items,
re-verified against the live codebase on 2026-08-02 where practical — not a
blind copy of the July numbers.

## Re-verified counts (2026-08-02) vs. the original July 15 snapshot

| Dimension | Jul 15 | Aug 2 (verified live) | Notes |
|---|---|---|---|
| Skills | 20 (5 existing + 15 new) | **29** (`vinu-agent/skills/`) | Grew, still far from the 87 target |
| Broker connectors | 1 (Alpaca) | **1** (Alpaca) — plus a new `performance_store.py` not in the original file list | No new broker added |
| IM channels | 2 (Telegram, Discord) | **2** (unchanged) | No WeChat/WhatsApp/Signal/Teams added |
| Web frontend | 0% | **0%** (confirmed: no `.tsx`/`package.json` anywhere in the repo) | Still nothing |
| Agent tool files | 17 tools (per the doc's count) | **28 files** in `vinu_agent/tools/` | Not a like-for-like count — some of the growth is from this session's own work elsewhere, verify individually before treating as "11 new tools" |
| Data loaders | 6 (Alpaca, Polygon, Yahoo, yfinance, tushare, stubs) | **5 real providers** confirmed (`alpaca.py`, `polygon.py`, `tushare.py`, `yahoo.py`, `yfinance.py`) | Roughly consistent, not re-expanded |
| MCP tools | 13 (stdio) | **not re-verified** — `mcp_server.py` wraps the live `ToolRegistry` dynamically rather than defining a fixed list, so the exposed count likely tracks the tool-file growth above, but this needs a live `list_tools` call to confirm, not a static grep | Don't trust either the old "13" or an assumed new number without checking |

## Backlog — "Not Yet Planned" (discovered during the July 15 implementation pass, never turned into a task)

| Item | Priority (as originally assessed) | Notes |
|---|---|---|
| Factor test suite for the 461 alpha factors | Medium | No dedicated alpha-factor test coverage exists |
| Factor monitoring / real-time streaming | Medium | Push factor values for watchlist symbols as they update |
| Regime detection → automatic factor selection | Medium | Use `regime_analysis` (now much more developed post this session's work) to pick which factors to weight |
| Composite factor construction | Low | Combine top-performing factors into a single blended signal |
| Factor decay agent tool | Medium | Wrap `factor_decay.py` as a callable agent tool |
| Factor expression agent tool | Medium | Let the agent validate/compose alpha expressions directly |
| Remaining data loaders (stooq, etc.) | Low | Listed in the original plan, never implemented |
| API doc generation | Low | Auto-generate API docs from the FastAPI routes |
| Full audit trail for trade submissions/rejections | Medium | Every order attempt (approved or blocked by `OrderGuard`) should be logged, not just successful ones |
| MCP tool expansion | Low | Original doc said 13→54; re-verify actual current exposed count first (see table above) before treating this as still a 41-tool gap |

## Backlog — larger unstarted scope (P3/P4 from the original plan)

| Item | Est. effort (original estimate, likely stale) | Still relevant? |
|---|---|---|
| Web frontend (React chat UI, backtest viewer, settings panel) | 2 weeks | Confirmed still 0% built. Relevance depends on whether a UI is actually wanted vs. staying API/agent-driven — not decided anywhere in current plans. |
| Remaining ~58 skills (29 exist now, original target 87) | ~2 days per original estimate (unlikely accurate at this scale) | Target of "87" was set relative to Vibe-Trading's skill count, not derived from vinu's own needs — worth re-deriving what skills are actually missing for *this* system's use cases rather than chasing a borrowed number. |
| 11 more broker connectors (stooq, eastmoney, ccxt, akshare, IBKR, Binance, etc.) | 3 weeks | Only relevant if trading non-US-equity markets is ever in scope. Current Stage 1/Stage 2 work (`e2e-test-0731/`, `the-stage-2-claude/`) is US-equities-only (AAPL/TSLA/JNJ via Alpaca) — no current plan needs this. |
| 14 more IM channels (WeChat, WhatsApp, Signal, Teams, etc.) | 2 weeks | Same — no current plan calls for this. Telegram + Discord already cover the "notify a human" need used by the confirmation flow. |

## How this relates to the other active plans

- **Does not overlap** with `the-stage-2-claude/` (scoped to `news_price_causality` improvements — peer comparison, classifier tuning — and Stage 2 paper-trading readiness). Different area of the codebase entirely (alpha-factor/agent tooling vs. news-analysis).
- **Does not overlap** with `e2e-test-0731/` (Stage 1 historical validation, now complete) or `e2e-test-0731/stage-2-plan.md` (paper trading definition).
- If any of the above ever becomes a real priority, it needs its own definition-phase plan (same discipline as the other two) before implementation — this file is a **candidate list**, not a committed plan.
