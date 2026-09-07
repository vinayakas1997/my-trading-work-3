# Full Pattern — 9 Edge Cases × 2 tickers (what wil happen per edge)

> Each edge is one `test_run_id` per ticker, same stage table as `03-full-runbook` but pushed off golden path. `what wil happen` is the signal a real bug lives where normal dev rarely exercises.

| # | Edge | Trigger (force or find) | What wil happen (pass condition) |
|---|---|---|---|
| 1 | Golden path one ticker no failures | Watchlist → SA → P triage → sweep PASS → APPROVED → funded → Live+Shadow → hold | All 7 stages `pass`, `TickerLedger` 7 rows in order, `composition_view` no gaps or gaps logged |
| 2 | Sweep `FAIL`→re-propose | Force bad recipe or find thin ticker | Reasoning reaches `P` loop-back `04:109`, next proposal `prior_rejections` includes it (not blind re-propose) |
| 3 | `risk_gatekeeper REJECTED` | High corr or over-size candidate | Stays `BENCHING` not discarded, reason → `P` + `SIG` (`decisions/09` records flag) |
| 4 | Kill mid-flow `PEND→PENDBLOCK` | `approved` then `POST /agent/broker/halt` before `900s` allocator | `PENDBLOCK` held not `ACTIVE`, storage never lies; after `resume` next cycle `mark_active` cleans, no duplicate |
| 5 | Thesis near-duplicate | Submit theory then near-duplicate within same cycle K-cap window | Second discarded by cheap `HR` + `K` check before LLM call `04:29` — cost-control proves |
| 6 | Thesis K-cap shared | Watchlist exhausts `K=3` for ticker then novel human theory same cycle | Deferred by **shared** counter, not accepted because Intake dup-check alone doesn't know watchlist usage |
| 7 | Rebalance `REQUEST` vs Monitor race same cycle | Emit `capital_allocator` `unwind REQUEST` while `Monitor` evaluating same symbol | `Monitor` `_evaluate_rebalance_request` declined if `favorable_move>5%`, otherwise `REQUEST` honored but Monitor retains `close` authority — rebalancer never closes directly `02-guard-rail.md` |
| 8 | Decay→`HR`→next `P` | Let open position decay to drop threshold (`decay`/`close-out`) | `HypothesisRegistry.add_evidence` written with `metrics_snapshot`, next `P` on that ticker reads it via `query_by_symbol` before proposing |
| 9 | Batch NEW-vs-NEW corr | 2 tickers `PEND` same `900s` batch | `evaluate-batch` includes both in same `correlation_matrix` vs each alone — `remaining_unallocated` reflects batch |

Run each edge for **≥2 tickers** (e.g. AAPL + MSFT) — one ticker passing doesn't prove generality. Record `manifest.jsonl` per ticker per edge with `UNIQUE(test_run_id,ticker,stage)`.
