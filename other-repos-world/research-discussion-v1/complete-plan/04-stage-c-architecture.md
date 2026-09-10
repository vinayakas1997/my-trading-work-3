# Stage C — Bigger Architecture (16 items)

**Not urgent by design.** These are real, valuable patterns — several of them close the gap with the most institutionally mature repos audited (pysystemtrade, StockSharp, NautilusTrader) — but each is a bigger structural change than anything in Stage A, and none of them are blocking Stage A or Stage B. Don't front-load this stage; revisit an item here only when something concrete in Stage A/B hits a limit that this specific item would resolve.

Unlike Stages A/B, this list is **not sequenced** — there's no natural build order between these items, and picking one over another should be driven by what Stage A/B work actually surfaces as a real need, not by this list's order.

Status key: `pending` · `in-progress` · `done` · `skipped` (reason) · `deferred` (still not needed).

| ID | Item | Target | Revisit trigger | Source |
|---|---|---|---|---|
| C1 | Executor-as-state-machine architecture for concurrent frozen trade plans | `vinu-live` | If Stage A's per-position items (A6-A14) start feeling like they need a shared lifecycle object instead of scattered orchestrator logic | Hummingbot → `06-hummingbot.md` |
| C2 | `IProtection`/`ProtectionReturn` lock abstraction generalizing halt-policy/cooldown | `vinu-live` | If Stage 0's G2 resolution or new halt-policy needs make the current ad hoc halt logic hard to extend | Freqtrade → `01-freqtrade.md` |
| C3 | Iceberg/TWAP client-side execution algorithms for large-order slicing | `vinu-live` | If position sizes grow enough that single-order execution starts moving the market noticeably | StockSharp → `10-stocksharp.md` |
| C4 | Override taxonomy (untradeable/reduce_only/ignored per symbol, with reasons + precedence resolution) | `vinu-live` | If the binary kill-switch/halt-policy model stops being expressive enough for real incidents | pysystemtrade → `12-pysystemtrade.md` (`diagOverrides`) |
| C5 | Ump-style GMM outcome-cluster veto as an additional statistical pre-trade gate | `vinu-live`/`vinu-agent` | Only after Stage 0's G1 (promotion gate wiring) is fixed and stable — this is an additional layer on top, not a substitute | abu → `07-abu.md` |
| C6 | Rule object + action enum decoupling — each TradingMandate limit as an independent Save/Load-able object | `vinu-agent` | If the runtime-settings admin API (Stage A's A21/A32) outgrows flat numeric knobs and needs per-rule structure | StockSharp → `10-stocksharp.md` |
| C7 | Persisted, queryable, independently-resettable per-instrument trade-limit storage | `vinu-agent` | If Stage A's A18 (rolling-window counter) proves insufficient for auditability needs | pysystemtrade → `12-pysystemtrade.md` (`dataTradeLimits`) |
| C8 | Min-of-4-independent-risk-multipliers scalar applied to order size, instead of binary reject/allow | `vinu-agent` | If binary reject/allow risk checks start feeling too blunt in practice | pysystemtrade → `12-pysystemtrade.md` |
| C9 | Exhaustive risk-override reason-code enum + valid-transition set | `vinu-agent` | If C4 (Override taxonomy) gets built — natural pairing, do together | daily_stock_analysis → `04-daily_stock_analysis.md` |
| C10 | Refactor TradingMandate checks into an independent, always-invoked checkpoint outside the agent loop | `vinu-agent` | Only if a code path is found that can submit an order without going through `OrderGuard` — otherwise this is process/audit hardening, not a functional fix | NautilusTrader → `03-nautilus_trader.md` |
| C11 | HRP as a backstop when the correlation matrix is ill-conditioned | `vinu-portfolio` | If Stage A's A1/A2 (PSD repair, shrinkage) aren't enough for a small/short-history universe | PyPortfolioOpt → `11-pyportfolioopt.md` |
| C12 | Risk-management-as-target-rescaling stage — operate on the full proposed target set post-construction | `vinu-portfolio` | If a real incident shows a multi-order sector-concentration breach that no single-order check caught | Lean → `05-lean.md` |
| C13 | Data-derived regime labeling (drawdown/run-up/slope-based) as an additional automatic stress-test dimension | `vinu-research` | If Stage A's A26 (PIT-leakage screening) and existing stress-test windows stop feeling comprehensive enough | TradeMaster (idea only — repo removed from disk) |
| C14 | `FillModel` trait's four hooks (is_limit_filled/is_slipped/fill_limit_inside_spread/synthetic book) as a swappable interface | `vinu-simulator` | If Stage A's A27-A31 individual fill-realism items need a shared interface instead of separate bolt-ons | NautilusTrader → `03-nautilus_trader.md` |
| C15 | Per-security-type fill model dispatch (illiquid small-cap vs liquid large-cap get different assumptions) | `vinu-simulator` | If backtest results start looking systematically wrong specifically for small/illiquid names | Lean → `05-lean.md` |
| C16 | Field-metadata-as-single-source-of-truth config registry | `vinu-infra` | If Stage A's A32 (atomic writes) proves insufficient and a UI or docs-generation need emerges for the runtime-settings API | daily_stock_analysis → `04-daily_stock_analysis.md` |
| C17 | `PAUSE_FOR_REAUTH` as a third OrderGuard outcome (between allow and reject) for borderline quantitative breaches, distinct from the existing unconditional `require_confirmation` gate | `vinu-agent` | If the binary pass/reject shape of individual OrderGuard checks starts feeling too blunt for near-threshold cases | Vibe-Trading → `14-vibe-trading.md` |
| C18 | Mandate consent expiry (`expires_at`) routing to re-authentication, instead of a mandate loaded once and trusted indefinitely | `vinu-agent` | If a real incident shows a stale/outdated mandate stayed in effect longer than intended | Vibe-Trading → `14-vibe-trading.md` |
| C19 | Five-layer ReAct context-management pipeline (prune → fold → LLM-summarize → explicit-trigger → incremental-update) for long multi-tool-call agent sessions | `vinu-agent` | If `vinu-agent`'s ReAct loop or a future LLM re-rank step in `vinu-screener` starts hitting context-window limits on long sessions | Vibe-Trading → `14-vibe-trading.md` (`agent/loop.py`) |

*(C17-C19 added 2026-09-10, once Vibe-Trading's real URL was found and it was fully audited.)*

## Notes

- Every "Revisit trigger" column entry is a judgment call, not a hard rule — the point is to have *a* stated reason to come back to each item, so revisiting Stage C isn't a vague "eventually" but tied to something concrete that would actually justify the bigger change.
- If an item here sits `deferred` for a long time with its trigger never firing, that's a sign it may genuinely not be needed — periodically reconsider whether some of these should just be marked `skipped`.
