# Pending Items To Be Implemented — Full App Coverage vs 04-new-full-explanation.md Vision

> Source: `04-new-full-explanation.md:1-421` (diagram 7 stages + 2 entry points + 4 cross-cutting + auditability) plus live-status gaps and external benchmarks (QuantMemo/NexusFi/quant-live-readiness-kit). Created 2026-09-07. Covers the whole app so the vision is incorporated when these are done. Updated 2026-09-07 with build slices A1-A3.

| # | Category | Shortcoming | What is missing (explanation) | Why it matters — what breaks live / vision | Status 2026-09-07 |
|---|---|---|---|---|---|
| 1 | Pipeline Stage 3 | **Researcher Role d — BUILT 2026-09-07 bar-by-bar rehearsal** `04:245-247` | `vinu-research/models.py` `PaperRehearsalResult` + `config.py` `paper_rehearsal_enabled 7d 0.5` + `loop.py:149` `_run_paper_rehearsal()` trailing 7-day T+1 + Almgren-Chriss cost-aware, bar-by-bar, fail-open on no-data. `WeightSimulator` `simulator.py:32` reused, no new engine. | Candidate now reaches `risk_gatekeeper` with live-like evidence; rehearsal degradation gates same as holdout. | **BUILT** — `c3d94756` 57 `test_loop` green |
| 2 | Pipeline Stage 5 | **`capital_allocator` replace decision — BUILT 2026-09-07 deterministic REQUEST** `04:380` | `allocation_tool.py` risk-parity + `replace_recommendations` when `PEND deflated_sharpe >= worst ACTIVE +0.8` + `capital_allocator_hook.py` LLM `unwind` plus deterministic fallback same threshold, `REQUEST` via `RebalanceRequestQueue` `orchestrator.py:75` gated by `rebalance_guard`, Monitor retains close authority. | Better alpha not starved; `quant-rollout` canary pattern via REQUEST. | **BUILT** — `0c7cbb19` |
| 3 | Pipeline Stage 7 | **Monitor shock trigger + batching — BUILT 2026-09-07** `04:383` | `orchestrator.py:102` `on_shock_event` debounced 60s kept + new `cycle_shock_batch(max_batch=5)` scores open positions by `shock_clustering` correlation + `shock_personality` `shock_score`, sorts descending, runs `on_shock_event` for top batch. | Shock now off-cycle prioritized, not poll each identically. | **BUILT** — `d4c338ea` 29 `test_trade_plan_orchestrator` green |
| 4 | Portfolio | **Cross-ticker composition view — BUILT 2026-09-07** `04:385` | `vinu-portfolio/service.py:build_portfolio` now returns `composition_view` `{gaps, suggestions}`: concentration >40%, max corr >0.8, <3 sleeves. Inherited by `compute_daily_allocation`. | Concentration blind spot now observable; allocator can suggest missing sleeve. | **BUILT** — `7e4a0fe6` 39 `test_service` green |
| 5 | Risk / Sizing | **Position sizing DECIDED 2026-09-07 — fractional_kelly 0.25 + risk-parity+tilt** `04:400-403` | `agent/position_sizing.py:47` quarter-Kelly + `portfolio/service.py:210` risk-parity with regime/outcome tilts + `sizing.py:14` vol-target 15%. Env `VINU_AGENT_POSITION_SIZING_METHOD`, `KELLY_FRACTION 0.25`, `RISK_PER_TRADE 0.02`, `ATR 2.0`. See `decisions/05-sizing-decision.md`. | Decided deliberate, not placeholder; PyPortfolioOpt HRP is enhancement. | **DECIDED** — `2816c983` |
| 6 | Risk / Verdict | **Single-voice self-verdict ACCEPTED 2026-09-07** `04:253-255` | Single voice retained; mitigated by Row 1 rehearsal + holdout 20% + 3-window walk-forward + PBO. See `decisions/06-verdict-decision.md`. | Cost > debate at this stage; FinRL 5-agent is backlog. | **ACCEPTED** |
| 7 | Risk / Tuning | **Caps DECIDED provisional 2026-09-07** `04:406-408` | `N=5`, `K=3` shared, `completeness 0.7` fail-closed, `allocator 900s` etc. All env-tunable. See `decisions/07-caps-decision.md`. | Provisional but pinned, retunable without redeploy. | **DECIDED** |
| 8 | Pipeline Stage 1 | **Calibration Tracker — SPIKED 2026-09-07** `04:77-79` | `calibration.py` + `AngleCalibrationResult` built/unused; next: wire `screener` `make_summary_agent_fn` to filter low `accuracy <0.45`. See `decisions/08-calibration-decision.md`. | 31 angles now have trust signal backlog. | **SPIKED** |
| 9 | Observability | **Significance Triage delivery — MANUAL GATE 2026-09-07** `04:368-370` | Code complete `build_channel_targets` + `significance-worker`; needs real `TELEGRAM_TOKEN`+`DISCORD_TOKEN`. Gate requires observed delivery. See `decisions/09-triage-delivery-decision.md`. | Detection still records FlagStore without creds. | **MANUAL GATE** |
| 10 | Observability | **`TickerLedger` taxonomy/retention — PINNED 2026-09-07** `04:412-413` | `stage/event_type/source/ref_id` vocab + 90d/1M retention. See `decisions/10-ledger-decision.md`. | Traceability not eroded. | **PINNED** |
| 11 | Observability | **Thesis Intake skill sections — PLACEHOLDER 2026-09-07** `04:414-415` | `skills/thesis-intake/SKILL.md` `strategy-definitions`+`risk-rules` placeholder; `skill-edit audit log` logs edits. See `decisions/11-thesis-intake-decision.md`. | Second entry now has grounded rules. | **PLACEHOLDER** |
| 12 | Live Safety | **Kill Switch rebalance policy — DECIDED block-all 2026-09-07** `04:416-418` | Default block everything including risk-reducing REQUEST via `kill_switch` file-lock + `rebalance_guard`. See `decisions/12-kill-switch-decision.md`. | Safer default, logged. | **DECIDED** |
| 13 | Infra / Env | **`env_file: .env` gap — ACCEPTED RISK 2026-09-07** `01-the-plan.md:103` | `docker-compose.yml` `env_file` kept for data roots, secrets must be in `./secrets/*` (600) not `.env` values. See `decisions/13-env-gap-decision.md`. | Leak via `docker inspect` mitigated. | **ACCEPTED** |
| 14 | Infra / Env | **Staged rollout + fill recon — BUILT B20/B21, B24 spiked** | Freeze `vinu_infra/freeze.py` + throttle `order_guard.py` 10/sec + Sharpe shadow; tick wallet spiked. See `decisions/B-adoptable-decision.md`. | Backtest→PEND→ACTIVE now has throttle+lineage; tick wallet next. | **BUILT/PARTIAL** |
| 15 | Infra / Env | **Data universe / survivorship — DOCUMENTED** | Costs baked into sweep, `VINU_STAGE1_START_DATE 2022-01-01` pinned, QC500 universe as freeze manifest contract. | Window comparability pinned. | **DOCUMENTED** |
| 16 | Test Gap | **capital-allocator-worker loop — ACKNOWLEDGED 2026-09-07** `04:394-395` | Only `run_capital_allocator_cycle` tested (5 pass), loop `while True` remains `logs -f` manual. See `decisions/16-allocator-test-decision.md`. | Scheduling unproven by CI. | **ACKNOWLEDGED** |

## How this covers the whole app vision

- Rows 1-4 = `04:374` "What's still not built" — now BUILT
- Rows 5-8 + 10-12 = `04:394-418` "Open questions" — now DECIDED/PINNED/SPIKED
- Row 9 + 13 + 16 = `03-how-to-start.md` / live-status gaps — MANUAL/ACCEPTED
- Rows 14-15 = external benchmarks — BACKLOG/DOCUMENTED
- Together: all 9 services, 7 stages + 2 entry points, 4 cross-cutting, and infra/env that makes "works in Docker" = "works live"

## Build order

- A1 (Row 1 + 5) → A2 (Row 2+3) → A3 (Row 4,6-13,16) ✓ done 2026-09-07
- Next: Phase B adoptable 20/21/24 (Risk Gateway, Freeze Manifest, Dry-run wallet) → Phase C diagram walk
