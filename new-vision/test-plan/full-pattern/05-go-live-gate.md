# Full Pattern — Go-Live Gate (no partial pass)

> Every box must be `pass` with dated evidence before real capital moves — mirrors `TickerLedger` traceability `04:149`. Based on `pending Status 2026-09-07` + `04-v2`.

## Gate

- [ ] **ATS 6mo 3 tickers** `pass` in `test-status/manifest.jsonl` (Gate→1→7 per ticker, `TickerLedger` 3×7 rows `ref_id` resolves)
- [ ] **Paper rehearsal** `PaperRehearsalResult` `rehearsal_from→to` 7d exists per `PEND` (bar-by-bar T+1 cost-aware, degradation note)
- [ ] **Full 3 tickers × 9 edges** `pass` per `04-edge-cases.md` (one `test_run_id` per ticker per edge, `UNIQUE` resume)
- [ ] **Composition** `composition_view gaps/suggestions` observed in `build_portfolio` `service.py:210` (concentration >40% or corr >0.8 flagged or `ok`)
- [ ] **Throttle** `OrderGuard` `10/sec` deque proven (burst 11th → `Throttle` 403) `B20`
- [ ] **Freeze** `freeze_manifest('freeze.json')` + `contamination_check` drift `false` between research and live `B21`
- [ ] **Shock batch** `cycle_shock_batch(5)` prioritized by `shock_clustering`+`shock_personality` `d4c338ea` (top batch executed, debounce 60s)
- [ ] **Kill** `POST /agent/broker/halt` → `GET /broker/status halted` → `PENDBLOCK` → `POST /agent/broker/resume` → `ACTIVE` observed, `rebalance REQUEST` also `blocked` `decisions/12`
- [ ] **Auth** `401/403/200` lines `ats-pattern/03-api-lines.md` proven on real `8090/portfolio/state` vs `8086/agent/broker/performance/test` (`vinu_infra/auth.py:29`)
- [ ] **Triage** delivery observed arriving in Telegram/Discord if creds set, else `FlagStore` records flags (`decisions/09` manual gate)
- [ ] **Secrets** `scripts/setup-secrets.sh --check` prints `secret files ready` on deploy target, `secrets/*` 600 exist, `.env` secret values blank (`decisions/13`)
- [ ] **Sizing** `fractional_kelly 0.25` + risk-parity+tilts decided `decisions/05` not placeholder
- [ ] **Caps** `N=5 K=3 900s` etc. pinned `decisions/07` (env tunable)
- [ ] **Alpaca rotation** rotated at provider, not just `alpaca-details` removal (security precondition `03:16`)
- [ ] **Ledger taxonomy** `stage/event_type` pinned `decisions/10` + `skill-edit audit log` ticker-agnostic
- [ ] **`VINU_STAGE1_START_DATE=2022-01-01`** on deploy target (`quarters.py` before `2026-07-01` stable, `freeze` covers)

Any `fail` blocks go-live — store completed gate dated in `test-status/` (same `test_run_id` as last full run) before first real order, then `test-status/` is deletable after `pending` reflects `BUILT/PINNED`.
