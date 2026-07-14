"""End-to-end test: real LLM-backed strategy refinement, cash tracking, and
manual (non-LLM) news download for MSFT (2023-01-01 to 2026-07-13).

Separate from integration_test.py (which fakes refinement with a manual grid
search). This script exercises the real StrategyResearchLoop against live
vinu-features / vinu-correlation / vinu-strategy / vinu-simulator / vinu-stock-price
services and a real local LLM, so it answers:

  1. How the strategy actually gets refined (real LLM candidate generation +
     real LLM risk critic, iteration by iteration).
  2. How cash was maintained (derived from the winning run's equity + weights
     curves: cash = portfolio_value * (1 - sum(weights))).
  3. How news and stock price data get downloaded (stock: raw paginated
     Alpaca HTTP; news: vinu-news backfill in manual mode, so it never calls
     the LLM analysis pipeline).
  4. How many LLM calls were made, with every prompt + response logged.

Uses MSFT specifically because AAPL already has cached data from prior runs
and would not exercise the download path.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import time
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
LOG = logging.getLogger("e2e_llm_test")

sys.path.insert(0, str(Path(__file__).resolve().parent / "vinu-components"))

SYMBOL = "MSFT"
FROM_YEAR, FROM_MONTH, FROM_DAY = 2023, 1, 1
TO_YEAR, TO_MONTH, TO_DAY = 2026, 7, 13
FROM_DATE = f"{FROM_YEAR}-{FROM_MONTH:02d}-{FROM_DAY:02d}"
TO_DATE = f"{TO_YEAR}-{TO_MONTH:02d}-{TO_DAY:02d}"

ROOT = Path(r"C:\Users\vinay\Desktop\my-trading-work-3")
DATA_DIR = ROOT / ".e2e_test_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ONEMIN_FILE = DATA_DIR / "stock" / f"{SYMBOL}_1min_full.parquet"
REPORT_FILE = DATA_DIR / "e2e_llm_report.json"
LLM_LOG_FILE = DATA_DIR / f"{SYMBOL.lower()}_llm_calls.json"

load_dotenv(ROOT / "vinu-components" / "vinu-stock-price" / ".env")
ALPACA_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_API_SECRET", "")
if not ALPACA_KEY or not ALPACA_SECRET:
    print("FATAL: ALPACA_API_KEY / ALPACA_API_SECRET not set")
    sys.exit(1)

DATA_BASE_URL = "https://data.alpaca.markets"
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

RESULT: dict[str, Any] = {
    "symbol": SYMBOL,
    "period": f"{FROM_DATE} to {TO_DATE}",
    "steps": [],
}

LIMITER = None


def fmt_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.2f} KB"
    return f"{b / (1024 * 1024):.2f} MB"


# =====================================================================
# STEP 0: Probe rate limit (seeds the pagination limiter)
# =====================================================================
def probe_rate_limit() -> Any:
    from vinu_lib.rate_limit import TokenBucket

    url = f"{DATA_BASE_URL}/v2/stocks/bars"
    params = {
        "symbols": SYMBOL,
        "timeframe": "1Min",
        "start": "2025-01-02T14:30:00Z",
        "end": "2025-01-02T14:31:00Z",
        "limit": "1",
    }
    detected_limit = 200
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        limit_h = resp.headers.get("X-RateLimit-Limit")
        if limit_h:
            detected_limit = int(limit_h)
    except requests.RequestException as e:
        LOG.warning("Rate limit probe failed: %s", e)
    return TokenBucket(rate=detected_limit, per=60)


# =====================================================================
# STEP 1: Stock price download (raw Alpaca HTTP, paginated by month)
# =====================================================================
def fetch_month_chunk(symbol: str, year: int, month: int) -> list[dict]:
    _, last_day = monthrange(year, month)
    start_iso = f"{year}-{month:02d}-01T00:00:00Z"
    end_day = last_day
    if year == TO_YEAR and month == TO_MONTH:
        end_day = min(last_day, TO_DAY)
    end_iso = f"{year}-{month:02d}-{end_day:02d}T23:59:59Z"

    url = f"{DATA_BASE_URL}/v2/stocks/bars"
    bars: list[dict] = []
    page_token: str | None = None

    while True:
        params: dict[str, str] = {
            "symbols": symbol,
            "timeframe": "1Min",
            "start": start_iso,
            "end": end_iso,
            "limit": "10000",
            "adjustment": "all",
        }
        if page_token:
            params["page_token"] = page_token

        LIMITER.acquire()
        resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
        if resp.status_code == 429:
            LOG.warning("429 rate limited on %s-%02d, backing off", year, month)
            LIMITER.wait()
            resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
        if resp.status_code == 403:
            params["feed"] = "iex"
            resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
        resp.raise_for_status()

        data = resp.json()
        chunk = data.get("bars", {}).get(symbol, [])
        bars.extend(chunk)

        page_token = data.get("next_page_token")
        if not page_token:
            break

    return bars


def step1_fetch_stock_price() -> pd.DataFrame:
    print("\n" + "=" * 65)
    print(f"  STEP 1: STOCK PRICE DOWNLOAD — {SYMBOL} 1-MIN BARS ({FROM_DATE} to {TO_DATE})")
    print("=" * 65)

    start_t = time.perf_counter()

    months: list[tuple[int, int]] = []
    for y in range(FROM_YEAR, TO_YEAR + 1):
        start_m = FROM_MONTH if y == FROM_YEAR else 1
        end_m = TO_MONTH if y == TO_YEAR else 12
        for m in range(start_m, end_m + 1):
            months.append((y, m))

    print(f"  Month chunks: {len(months)}  |  parallel workers: 4")

    all_bars: list[dict] = []
    chunk_results: list[dict] = []
    errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fut_map = {
            pool.submit(fetch_month_chunk, SYMBOL, y, m): (y, m)
            for y, m in months
        }
        for fut in concurrent.futures.as_completed(fut_map):
            y, m = fut_map[fut]
            try:
                chunk_bars = fut.result()
                all_bars.extend(chunk_bars)
                chunk_results.append({"month": f"{y}-{m:02d}", "bars": len(chunk_bars)})
                print(f"    {y}-{m:02d}: {len(chunk_bars):>6,} bars")
            except Exception as e:
                errors.append(f"{y}-{m:02d}: {e}")
                print(f"    {y}-{m:02d}: ERROR — {e}")

    elapsed = time.perf_counter() - start_t

    if not all_bars:
        print("  FATAL: No 1-min bars fetched!")
        RESULT["steps"].append({"name": "1. Stock Price Download", "status": "FAIL", "elapsed_sec": round(elapsed, 2)})
        return pd.DataFrame()

    df = pd.DataFrame(all_bars)
    df.rename(columns={
        "t": "timestamp", "o": "open", "h": "high",
        "l": "low", "c": "close", "v": "volume",
        "n": "trade_count", "vw": "vwap",
    }, inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    import pyarrow as pa
    import pyarrow.parquet as pq
    ONEMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df), str(ONEMIN_FILE))
    disk_size = ONEMIN_FILE.stat().st_size

    step = {
        "name": "1. Stock Price Download",
        "status": "PASS" if not errors else "PARTIAL",
        "symbol": SYMBOL,
        "total_bars": len(df),
        "chunks": len(months),
        "errors": len(errors),
        "disk_bytes": disk_size,
        "disk_bytes_human": fmt_bytes(disk_size),
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    print(f"\n  Total 1-min bars: {len(df):,}  |  Disk: {fmt_bytes(disk_size)}  |  Time: {elapsed:.1f}s  |  {step['status']}")
    return df


def resample_to_daily(df_1min: pd.DataFrame) -> pd.DataFrame:
    df = df_1min.set_index("timestamp").copy()
    ohlc = {
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "trade_count": "sum",
    }
    df_daily = df.resample("1D").agg(ohlc).dropna(subset=["open"])
    df_daily.reset_index(inplace=True)
    df_daily.rename(columns={"timestamp": "ts"}, inplace=True)
    df_daily["ts"] = df_daily["ts"].dt.strftime("%Y-%m-%d")
    return df_daily


# =====================================================================
# STEP 2: News download — manual mode, no LLM analysis
# =====================================================================
def step2_download_news() -> dict:
    print("\n" + "=" * 65)
    print(f"  STEP 2: NEWS DOWNLOAD (manual, no LLM) — {SYMBOL} since {FROM_DATE}")
    print("=" * 65)

    start_t = time.perf_counter()

    news_env_path = ROOT / "vinu-components" / "vinu-news" / ".env"
    load_dotenv(news_env_path, override=True)

    news_db_path = DATA_DIR / "news" / f"{SYMBOL.lower()}_news.db"
    news_db_path.parent.mkdir(parents=True, exist_ok=True)

    os.environ["VINU_NEWS_DB_PATH"] = str(news_db_path)
    os.environ["VINU_NEWS_STORAGE"] = "sqlite"
    os.environ["VINU_LLM_ANALYSIS_MODE"] = "manual"

    from vinu_news.service import NewsService

    with NewsService() as svc:
        settings_before = svc.get_settings()
        assert settings_before.llm_analysis_mode == "manual", (
            f"expected manual mode, got {settings_before.llm_analysis_mode!r} — "
            "refusing to risk an LLM analysis call during download"
        )
        svc.patch_settings(backfill_start_date=FROM_DATE, llm_analysis_mode="manual")
        result = svc.run_backfill_single(SYMBOL)

    elapsed = time.perf_counter() - start_t
    disk_size = news_db_path.stat().st_size if news_db_path.exists() else 0

    step = {
        "name": "2. News Download (manual, no LLM)",
        "status": "PASS" if result.get("status") in ("completed", "paused") else "FAIL",
        "symbol": SYMBOL,
        "backfill_result": result,
        "llm_analysis_mode": "manual",
        "disk_bytes": disk_size,
        "disk_bytes_human": fmt_bytes(disk_size),
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    print(f"  Backfill result: {result}")
    print(f"  Disk: {fmt_bytes(disk_size)}  |  Time: {elapsed:.1f}s  |  {step['status']}")
    return step


# =====================================================================
# STEP 3: Real LLM-backed strategy refinement
# =====================================================================
class LlmCallLogger:
    """Wraps ResearchLlmClient.chat_json to log every prompt + response and
    count calls by type, without touching production code."""

    def __init__(self, llm_client: Any):
        self._llm = llm_client
        self._orig_chat_json = llm_client.chat_json
        self.calls: list[dict[str, Any]] = []
        self._critic_calls_seen = 0
        llm_client.chat_json = self._wrapped_chat_json  # type: ignore[method-assign]

    @staticmethod
    def _classify(system: str) -> str:
        if "writes trading strategy code" in system:
            return "candidate_generation"
        if "senior quantitative risk analyst" in system:
            return "risk_critic"
        return "unknown"

    async def _wrapped_chat_json(self, system: str, user: str):
        call_type = self._classify(system)
        iteration = self._critic_calls_seen + 1
        t0 = time.perf_counter()
        response = await self._orig_chat_json(system, user)
        elapsed = time.perf_counter() - t0

        self.calls.append({
            "call_index": len(self.calls) + 1,
            "iteration": iteration,
            "call_type": call_type,
            "system_prompt": system,
            "user_prompt": user,
            "response": response,
            "elapsed_sec": round(elapsed, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if call_type == "risk_critic":
            self._critic_calls_seen += 1
        return response


async def step3_strategy_refinement() -> tuple[dict, str | None]:
    print("\n" + "=" * 65)
    print("  STEP 3: REAL LLM-BACKED STRATEGY REFINEMENT")
    print("=" * 65)

    start_t = time.perf_counter()

    from vinu_research.config import ResearchConfig
    from vinu_research.loop import StrategyResearchLoop

    research_config = ResearchConfig(
        max_iterations=5,
        llm_candidates=1,  # local thinking model serializes concurrent calls (~194s each);
                            # 3 candidates concurrently blew past even a 280s timeout
        llm_enabled=True,
        llm_base_url="http://localhost:7000/v1",
        llm_model="qwen36-35b-vision",
        llm_ttl_sec=0,  # disable cache — every call must be a real live LLM call
        llm_timeout_sec=400.0,  # local thinking model needs headroom beyond the 120s default
        generator_mode="hybrid",
        data_root=DATA_DIR / "research",
        initial_capital=1_000_000.0,
    )

    loop = StrategyResearchLoop(config=research_config)
    assert loop._llm is not None, "LLM client not constructed — llm_enabled did not take"
    logger = LlmCallLogger(loop._llm)

    user_idea = (
        "SMA 20/50 crossover on MSFT, long when fast SMA > slow SMA, flat "
        "otherwise, with an RSI(14) filter to skip entries when RSI > 70 "
        "(overbought)."
    )

    try:
        research_result = await loop.run(
            user_idea=user_idea,
            symbol=SYMBOL,
            from_date=FROM_DATE,
            to_date=TO_DATE,
            indicators=["sma_20", "sma_50", "rsi_14"],
            initial_capital=1_000_000.0,
        )
    finally:
        await loop._llm.close()
        await loop._tools.close()

    elapsed = time.perf_counter() - start_t

    LLM_LOG_FILE.write_text(json.dumps(logger.calls, indent=2, default=str))

    call_counts = {"candidate_generation": 0, "risk_critic": 0, "unknown": 0}
    for c in logger.calls:
        call_counts[c["call_type"]] = call_counts.get(c["call_type"], 0) + 1

    iterations_out = []
    for rec in research_result.iterations:
        m = rec.result.metrics
        iterations_out.append({
            "iteration": rec.iteration,
            "sharpe": round(m.sharpe_ratio, 3),
            "return_pct": round(m.total_return * 100, 2),
            "max_dd_pct": round(m.max_drawdown * 100, 2),
            "win_rate_pct": round(m.win_rate * 100, 1),
            "trades": rec.result.trade_count,
            "verdict": rec.critique.verdict,
            "run_id": rec.result.run_id,
        })

    best = research_result.best_result
    holdout = research_result.holdout
    step = {
        "name": "3. Strategy Refinement (real LLM loop)",
        "status": "PASS" if best is not None else "FAIL",
        "symbol": SYMBOL,
        "user_idea": user_idea,
        "total_iterations": research_result.total_iterations,
        "best_iteration": research_result.best_iteration,
        "iterations": iterations_out,
        "best_run_id": best.run_id if best else None,
        "best_sharpe": round(best.metrics.sharpe_ratio, 3) if best else None,
        "holdout": {
            "passed": holdout.passed,
            "in_sample_sharpe": round(holdout.in_sample_sharpe, 3),
            "holdout_sharpe": round(holdout.holdout_sharpe, 3),
            "note": holdout.note,
        } if holdout else None,
        "llm_calls_total": len(logger.calls),
        "llm_calls_by_type": call_counts,
        "llm_call_log_file": str(LLM_LOG_FILE),
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    print(f"\n  Iterations run:      {research_result.total_iterations}")
    for it in iterations_out:
        print(f"    Iter {it['iteration']}: Sharpe={it['sharpe']:.3f} Return={it['return_pct']:.1f}% "
              f"MaxDD={it['max_dd_pct']:.1f}% Trades={it['trades']} Verdict={it['verdict']}")
    print(f"  Best iteration:      {research_result.best_iteration}")
    print(f"  Holdout:             {step['holdout']}")
    print(f"  LLM calls total:     {len(logger.calls)}  ({call_counts})")
    print(f"  LLM call log:        {LLM_LOG_FILE}")
    print(f"  Time:                {elapsed:.1f}s  |  {step['status']}")

    return step, (best.run_id if best else None)


# =====================================================================
# STEP 4: Cash maintained — derived from equity + weights curves
# =====================================================================
async def step4_cash_maintained(run_id: str | None) -> dict:
    print("\n" + "=" * 65)
    print("  STEP 4: CASH MAINTAINED (derived from equity + weights)")
    print("=" * 65)

    start_t = time.perf_counter()

    if not run_id:
        step = {"name": "4. Cash Maintained", "status": "SKIPPED", "reason": "no winning run_id", "elapsed_sec": 0.0}
        RESULT["steps"].append(step)
        print("  SKIPPED — no winning run to inspect")
        return step

    simulator_url = "http://127.0.0.1:8085"
    async with httpx.AsyncClient(base_url=simulator_url, timeout=30.0) as client:
        eq_resp = await client.get(f"/results/{run_id}/equity")
        eq_resp.raise_for_status()
        equity = eq_resp.json()

        w_resp = await client.get(f"/results/{run_id}/weights")
        w_resp.raise_for_status()
        weights = w_resp.json()

    eq_df = pd.DataFrame(equity)
    w_df = pd.DataFrame(weights)

    elapsed = time.perf_counter() - start_t

    if eq_df.empty or w_df.empty:
        step = {"name": "4. Cash Maintained", "status": "FAIL", "reason": "empty equity/weights", "elapsed_sec": round(elapsed, 2)}
        RESULT["steps"].append(step)
        print("  FAIL — empty equity or weights curve")
        return step

    eq_df["date"] = eq_df["date"].astype(str)
    merged = eq_df.merge(w_df, on="date", how="inner")
    ticker_cols = [c for c in w_df.columns if c != "date"]
    merged["invested_weight"] = merged[ticker_cols].abs().sum(axis=1)
    merged["cash_weight"] = (1.0 - merged["invested_weight"]).clip(lower=None)
    merged["cash_value"] = merged["cash_weight"] * merged["portfolio_value"]

    step = {
        "name": "4. Cash Maintained",
        "status": "PASS",
        "run_id": run_id,
        "days": len(merged),
        "start_cash": round(float(merged["cash_value"].iloc[0]), 2),
        "end_cash": round(float(merged["cash_value"].iloc[-1]), 2),
        "min_cash": round(float(merged["cash_value"].min()), 2),
        "max_cash": round(float(merged["cash_value"].max()), 2),
        "mean_cash_pct_of_nav": round(float(merged["cash_weight"].mean() * 100), 2),
        "pct_days_fully_invested": round(float((merged["cash_weight"] < 0.01).mean() * 100), 1),
        "start_nav": round(float(merged["portfolio_value"].iloc[0]), 2),
        "end_nav": round(float(merged["portfolio_value"].iloc[-1]), 2),
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    cash_curve_file = DATA_DIR / f"{SYMBOL.lower()}_cash_curve.csv"
    merged[["date", "portfolio_value", "cash_weight", "cash_value"]].to_csv(cash_curve_file, index=False)
    step["cash_curve_file"] = str(cash_curve_file)

    print(f"  Days:                {step['days']}")
    print(f"  Start cash:          ${step['start_cash']:,.2f}  (NAV ${step['start_nav']:,.2f})")
    print(f"  End cash:            ${step['end_cash']:,.2f}  (NAV ${step['end_nav']:,.2f})")
    print(f"  Min/Max cash:        ${step['min_cash']:,.2f} / ${step['max_cash']:,.2f}")
    print(f"  Mean cash % of NAV:  {step['mean_cash_pct_of_nav']:.2f}%")
    print(f"  % days fully invested (<1% cash): {step['pct_days_fully_invested']:.1f}%")
    print(f"  Cash curve saved to: {cash_curve_file}")
    print(f"  Time:                {elapsed:.1f}s  |  PASS")

    return step


# =====================================================================
# MAIN
# =====================================================================
async def async_main():
    global LIMITER
    overall_start = time.perf_counter()

    LIMITER = probe_rate_limit()

    df_1min = step1_fetch_stock_price()
    if df_1min.empty:
        print("FATAL: stock price download failed, aborting")
        sys.exit(1)

    step2_download_news()

    strategy_step, best_run_id = await step3_strategy_refinement()

    await step4_cash_maintained(best_run_id)

    overall_elapsed = time.perf_counter() - overall_start

    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    for s in RESULT["steps"]:
        print(f"  {s['name']:<45} {s['status']:<10} {s.get('elapsed_sec', 0):.1f}s")
    print(f"\n  Overall time: {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} min)")
    print(f"  Test date:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    RESULT["overall_elapsed_sec"] = round(overall_elapsed, 2)
    with open(REPORT_FILE, "w") as f:
        json.dump(RESULT, f, indent=2, default=str)
    print(f"\n  Full report: {REPORT_FILE}")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
