# 01 — Pending vs Outer Coverage Matrix (16 × 18)

> Matrix showing which pending row is covered by which outer repo's mature handling. Source: `pending-items-to-be-implemented.md` (16 rows) vs `05-other-repos-research.md` (18 repos). Sep 2026.

## Covered (≥1 outer repo gives extractable logic)

| # | Pending Row | Best covering repo(s) | Coverage | What to extract |
|---|---|---|---|---|
| 1 | Role d rehearsal `04:245` | **Freqtrade** lookahead/recursive guard + **VectorBT** vectorized walk-forward + **Nautilus** Parquet replay | **Good** | Borrow leak test `tests/test_custom_sim.py:98` pattern + fast matrix walk |
| 2 | Replace decision `04:380` | `FinRL-X` promotion gate, `quant-rollout` canary (cited, not in 05) | **Partial** | Gate pattern (WR≥70% N trades + kill if WR<50% last 30) |
| 4 | Composition view `04:385` | **Qlib** factor/portfolio opt, **PyPortfolioOpt** HRP | **Good** | HRP missing-exposure check |
| 5 | Sizing provisional `04:400` | **PyPortfolioOpt** HRP/BL/L2, **pysystemtrade** forecast→position, **FinRL** MVO baseline | **Good** | HRP/L2 swap for `vinu-agent/config.py:106` |
| 6 | Single-voice verdict `04:253` | **FinRL** 5-agent bake-off, **TradeMaster** PRIDE-Star | **Good** | Adversarial baseline (A2C/DDPG/PPO vs MVO) |
| 7 | Untuned N/K `04:406` | **Lean Optimizer**, **Freqtrade hyperopt**, **VectorBT** broadcast | **Good** | Bayesian sweep tuner for K/N/completeness |
| 8 | Calibration Tracker unused `04:77` | **Qlib** model monitoring, **Lean** research calibration | **Partial** | Concept — wire tracker into `angle_synthesizer` |
| 9 | Triage delivery `04:368` | **daily_stock_analysis** multi-notify, **Freqtrade** Telegram/WebUI | **Good** | Notify plumbing |
| 14 | Staged rollout + fill recon | **Nautilus** deterministic fills/latency + **Lean** live parity | **Good** | Tick-level fill diff (not Sharpe-only `shadow_evaluator.py:23-129`) |
| 15 | Universe/PIT `04:77` | **Qlib** PIT DB (Mar 2022) + **Lean** QC500 universe | **Good** | PIT contract in `vinu-initial-analysis` quarters |
| 16 | Allocator test gap `04:394` | Lean/Qlib scheduler loop CI | **Partial** | Test pattern only |

## Not covered — must build custom (no outer repo solves it)

| # | Pending Row | Why no coverage |
|---|---|---|
| 3 | Monitor shock batching `orchestrator.py:100` | `shock_clustering/shock_personality` angle + batch prioritize across positions is unique to your 31-angle design; `Hummingbot` inventory is different domain |
| 10 | TickerLedger taxonomy/retention `ticker_ledger.py:19` | `TickerLedger` append-only `ref_id` discipline is your invention; Qlib/Lean log to DB but don't define `event_type` vocabulary |
| 11 | Thesis Intake skill sections `04:32` | `Qlib RD-Agent` helps factor search, but `load_skill` + `skill-edit audit log` `04:104` is your agentic gateway — content must be authored |
| 12 | Kill Switch risk-reducing rebalance `04:416` | Every repo has kill switch, but "block even risk-reducing unwind?" is your `rebalance_guard` policy `04:355` — business rule |
| 13 | `env_file: .env` gap `docker-compose.yml:9` | Infra gap, not quant feature — must change compose/`secrets_loader.py:44` |

## Summary

- **11/16 covered** (at least partial) from 18 repos — quant-heavy rows.
- **5/16 Vinu-specific** — remain pending even after extracting everything in 05; need custom build/spec, not cloning.

## Next

- For covered rows → open `03-per-repo-deep-dive/<repo>.md` and copy `source → dest` mapping.
- For not-covered → build per `04-implementation-slices.md` custom slice.
