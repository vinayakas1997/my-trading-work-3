# UI Status - Single View + Gaps + Repos Extras + Top (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `17`. Related: `04-full-progress-db-plan.md`, `15`, `16`.
Status: UI step closed with 3 gaps + 3 extras + 1 top = 7 total. Code steps ready to build next, no code changed yet in this doc.

---

## What UI must read today (5 places, no single view)

1. Health all 9 services. `GET /agent/health`, `/news/health`, `/stock/health`, `/features/health`, `/analysis/health`, `/strategy/health`, `/simulator/health`, `/research/health`, `/portfolio/health`, `/live/health`. File `vinu-agent/server/routes_system.py:15`. Today check logs + compose ps one by one.
2. Summary per ticker. `TickerSummaryStore` file `vinu-agent/storage/ticker_summaries.py:88`. `get_summary`, `list_summaries`. Has `27/27 1D` + agree and diverge text. UI first card.
3. Ledger events per ticker. `TickerLedger` routes file `vinu-agent/server/routes_ticker_ledger.py`. `candidate_proposed`, close-out rows with `ref_id`. Shows K-cap + stage flow.
4. Artifacts ranked + paper. Research `GET /research/artifacts?status=BENCHING or ACTIVE`, hypotheses, plus agent `GET /broker/performance/{id}` daily returns. File `vinu-agent/server/routes_broker.py:114`. Shows top 3 + paper Sharpe + degradation.
5. Sim + live books. Sim `simulations/ab/run_id/equity.parquet` curve + `trades.parquet`. Live `trade_plan_book.db` open and closed + `paper_performance.db`. Shows PnL + holds + exits.

Today you ask how much done, check 5 DBs. Inefficiency. Same as `04` plan.

---

## 3 gaps for UI (inefficiencies)

### 1. No one checkbox query
Need `full_progress.db` view `ticker + format + angle + stage + status pending running done error + run_id + interval`. File `04-full-progress-db-plan.md` exists, not built.
UI reads 1 SELECT, not 5 DBs. Example: `AAPL 1D 27/27 done`, `AAPL 1H 12/28 running`.
Fix first. Workers write checkbox on each stage done. Read-only UI reads it.
Status: Open.

### 2. No pipeline 0 to 7 page
Need 1 page: top watchlist vs thesis, 1D 27/27, 1H 28/28, sweep ranked 3, rehearsal pass, BENCHING 6, paper 6, ACTIVE 1 to 2, monitor hold or exit. Each row links to run_id + artifact_id.
Fix second. Read-only tables from 5 APIs above + full_progress view.
Status: Open.

### 3. No trade evidence drill-down
Need click run_id = equity curve + trades + regime + conditions + overlap 4 columns backtest vs rehearsal vs paper vs live. Click artifact = code + metrics + validation + paper Sharpe.
Today logs only. Fix third. Same data as `14-simulation-storage.md`, just UI view.
Status: Open.

---

## 3 advanced from other repos on top

### 4. Freqtrade freqUI tables
Pairlist + edge table + hyperopt results ranked + dry-run wallet fills. Adopt ranked table + wallet fills view. Low, read-only tables from sweep_grid + shadow wallet. No new compute.
Status: Open.

### 5. Lean QC dashboard + Nautilus admin
Consolidators + throttle + halt state + reconciliation diff book vs broker. Adopt halt banner + reconcile diff view. Banner shows `HALT_ENTRIES` vs `HALT_ALL` + reason. Diff shows expected vs actual positions + value. Small. Reads breaker + reconciler. File `trade_plan/orchestrator.py:658`, `breaker/limits.py:9`.
Status: Open.

### 6. Qlib notebooks + VectorBT plots + cpz-quant viz
Frontier, drawdown underwater, corr clusters ordered by HRP. Adopt equity + underwater + corr cluster plots. Low Plotly, read-only. Never import Plotly unless used. Same pattern as cpz-quant viz optional.
Status: Open.

---

## 1 more on top (added so nothing missed)

### 7. Export + alerts
Tables need CSV export per page + significance flags delivery state. Worker already detects large funding, repeated rejection, thesis contradiction. UI must show flag + delivered yes or no + mute button. Telegram Discord channels planned, UI shows state. Plus export `full_progress.csv`, `ranked.csv`, `paper.csv` for offline read. Small, prevents screenshot copying.
Auth uses existing `VINU_API_KEY` internal header, no new login v1. Refresh 10s knob. Desktop first, mobile later.
Knobs: `VINU_UI_ENABLED=true`, `VINU_UI_PORT=8092`, `VINU_UI_REFRESH_SEC=10`.
Status: Open.

---

## Knobs full list for UI (add to 10 later build)

- `VINU_UI_ENABLED=true`, `VINU_UI_PORT=8092`, `VINU_UI_REFRESH_SEC=10`.
- `VINU_UI_READ_ONLY=true`: true v1 no buttons, false later allows close position button. Buttons later after read stable. Avoids fat-finger live exit.
- Existing kept: all API URLs in `.env-example:64`, `VINU_API_KEY` auth, `VINU_AGENT_DATA_ROOT`, `VINU_RESEARCH_DATA_ROOT`. No duplicate.
- Future timeframe: same `VINU_SWEEP_INTERVALS` drives UI rows, no extra knob. New interval appears auto.

---

## Order to build (read-only first, closed 7)

1. Checkbox view + pipeline 0 to 7 page. 1-2 together. Highest value. Small. Read 5 APIs + 1 SELECT.
2. Drill-down + freqUI tables. 3-4 together. Medium small. After 1 green. Curves + ranked.
3. Halt banner + reconcile diff + plots + export alerts. 5-7 together. After 2 green. Safety banner + viz + CSV.
4. Test: health all green, pipeline counts match DB, drill-down loads equity, halt banner shows on HALT, export downloads CSV, refresh 10s no 429.

After 1-4, UI done. Read-only v1. Buttons v2 later. Next is data pipeline upstream + portfolio inside + learning. Different docs.

---
Link: Data pipeline 4 gaps + 3 extras + 2 top is in `18-data-pipeline.md`. 17 -> 18 = UI -> data closed.

---

## All covered proof (nothing missed for UI)

- APIs `routes_system.py:15` health, `routes_ticker_ledger.py` ledger, `routes_broker.py:114` performance, `ticker_summaries.py:88` summary, research artifacts + hypotheses, sim parquet + live books. All listed.
- Gaps mapped: `04` full_progress view 1 here, pipeline page 2 here, `14` drill-down 3 here.
- Repos mapped: Freqtrade freqUI 4 here, Lean + Nautilus admin 5 here, Qlib + VectorBT + cpz-quant viz 6 here. No new repo needed.
- Significance + Telegram Discord delivery state here 7, not lost.
- Read-only guard + no live buttons v1 here. Auth existing key. Refresh knob.
- 09 top3, 10 knobs, 11 paper all 6, 12 seven-day 10, 13 risk full, 14 storage full, 15 monitor closed, 16 broker closed kept. 17 closes UI.
