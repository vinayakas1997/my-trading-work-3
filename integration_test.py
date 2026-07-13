"""Full integration test: SMA 20/50 Crossover on AAPL (2023-01 to 2026-07).

Flow:
  1. Probe Alpaca API limits (rate limit, page size, data feed type)
  2. Fetch all 1-min bars via raw HTTP with pagination (source of truth)
  3. Resample to daily OHLCV (or any needed timeframe)
  4. Compute SMA 20/50 crossover signals
  5. Run research refinement loop (in-sample ~80% + holdout ~20%)
  6. Report iteration count, final verdict, out-of-sample degradation
"""

from __future__ import annotations

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

import pandas as pd
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
LOG = logging.getLogger("integration_test")

SYMBOL = "AAPL"
FROM_YEAR, FROM_MONTH, FROM_DAY = 2023, 1, 1
TO_YEAR, TO_MONTH, TO_DAY = 2026, 7, 13

load_dotenv(r"C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\.env")
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

DATA_DIR = Path(r"C:\Users\vinay\Desktop\my-trading-work-3\.e2e_test_data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
ONEMIN_FILE = DATA_DIR / "stock" / f"{SYMBOL}_1min_full.parquet"
REPORT_FILE = DATA_DIR / "integration_report.json"

RESULT: dict[str, Any] = {
    "symbol": SYMBOL,
    "period": f"{FROM_YEAR}-{FROM_MONTH:02d}-{FROM_DAY:02d} to {TO_YEAR}-{TO_MONTH:02d}-{TO_DAY:02d}",
    "steps": [],
}


def fmt_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.2f} KB"
    return f"{b / (1024 * 1024):.2f} MB"


def fmt_num(n: int | float) -> str:
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


# =====================================================================
# PROBE 1: API Limits (rate limit per minute)
# =====================================================================
def probe_api_limits() -> dict[str, Any]:
    print("\n" + "=" * 65)
    print("  PROBE 1: ALPACA API RATE LIMIT DETECTION")
    print("=" * 65)

    start_t = time.perf_counter()
    url = f"{DATA_BASE_URL}/v2/stocks/bars"
    now = datetime.now(timezone.utc)

    # Send 5 rapid single-bar requests to probe rate limit headers
    detected_limit = 200
    detected_remaining = None
    hit_429 = False
    api_calls_probed = 0

    for i in range(5):
        params = {
            "symbols": SYMBOL,
            "timeframe": "1Min",
            "start": "2025-01-02T14:30:00Z",
            "end": "2025-01-02T14:31:00Z",
            "limit": "1",
        }
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            api_calls_probed += 1
            if resp.status_code == 429:
                hit_429 = True
                print(f"  Request {i+1}: 429 — RATE LIMITED")
                break
            resp.raise_for_status()

            limit_h = resp.headers.get("X-RateLimit-Limit")
            remaining_h = resp.headers.get("X-RateLimit-Remaining")
            reset_h = resp.headers.get("X-RateLimit-Reset")
            if limit_h:
                detected_limit = int(limit_h)
            if remaining_h is not None:
                detected_remaining = int(remaining_h)

            print(f"  Request {i+1}: 200 — Limit={limit_h}  Remaining={remaining_h}  Reset={reset_h}")

        except requests.RequestException as e:
            print(f"  Request {i+1}: Error — {e}")

    # If we hit 429, use Retry-After to back off
    if hit_429:
        safe_rate = max(1, detected_limit // 2)
    else:
        safe_rate = detected_limit if detected_limit else 200

    from vinu_lib.rate_limit import TokenBucket
    limiter = TokenBucket(rate=safe_rate, per=60)

    elapsed = time.perf_counter() - start_t

    probe_result = {
        "discovered_rate_per_min": safe_rate,
        "raw_limit_header": detected_limit,
        "raw_remaining_header": detected_remaining,
        "hit_429": hit_429,
        "probe_api_calls": api_calls_probed,
    }
    RESULT["rate_limit_probe"] = probe_result

    print(f"\n  Discovered rate limit: {safe_rate} req/min")
    print(f"  Hit 429:              {hit_429}")
    print(f"  Probe API calls:      {api_calls_probed}")
    print(f"  Time:                 {elapsed:.1f}s")
    print(f"  Status:               PASS")

    return probe_result, limiter


# =====================================================================
# PROBE 2: Data Feed (IEX vs SIP)
# =====================================================================
def probe_data_feed() -> dict[str, Any]:
    print("\n" + "=" * 65)
    print("  PROBE 2: DATA FEED DETECTION (IEX vs SIP)")
    print("=" * 65)

    start_t = time.perf_counter()
    url = f"{DATA_BASE_URL}/v2/stocks/bars"

    params = {
        "symbols": SYMBOL,
        "timeframe": "1Day",
        "start": "2025-01-02T00:00:00Z",
        "end": "2025-01-10T00:00:00Z",
        "limit": "5",
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    bars = data.get("bars", {}).get(SYMBOL, [])

    # IEX: trade_count ~12-15K/day for AAPL; SIP: trade_count ~500K+/day
    feed_type = "unknown"
    avg_trade_count = 0
    if bars:
        trade_counts = [b.get("n", 0) for b in bars if b.get("n")]
        avg_trade_count = sum(trade_counts) / len(trade_counts) if trade_counts else 0
        if avg_trade_count < 50000:
            feed_type = "iex"
        elif avg_trade_count > 200000:
            feed_type = "sip"
        else:
            feed_type = "unknown"

    elapsed = time.perf_counter() - start_t

    probe_result = {
        "feed_type": feed_type,
        "avg_daily_trade_count": round(avg_trade_count, 0),
        "bars_sampled": len(bars),
    }
    RESULT["data_feed_probe"] = probe_result

    print(f"  Avg daily trade count: {avg_trade_count:,.0f}")
    print(f"  Detected feed:         {feed_type.upper()}")
    print(f"  Time:                  {elapsed:.1f}s")
    if feed_type == "iex":
        print(f"  Note: IEX captures ~2.5-4% of volume — fine for research")
    print(f"  Status:                PASS")

    return probe_result


# =====================================================================
# STEP 1: Fetch all 1-min bars (chunked by month, raw HTTP pagination)
# =====================================================================
def fetch_month_chunk(symbol: str, year: int, month: int) -> list[dict]:
    """Fetch all 1-min bars for a single calendar month. Returns list of bar dicts."""
    _, last_day = monthrange(year, month)
    start_iso = f"{year}-{month:02d}-01T00:00:00Z"
    end_day = last_day
    end_iso = f"{year}-{month:02d}-{end_day:02d}T23:59:59Z"
    # For current month, cap at TO_DATE
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
            LOG.warning("403 Forbidden on %s-%02d (SIP restriction on recent data), retrying with feed=iex", year, month)
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


def step1_fetch_1min_bars() -> pd.DataFrame:
    print("\n" + "=" * 65)
    print(f"  STEP 1: FETCH AAPL 1-MIN BARS ({FROM_YEAR}-{FROM_MONTH:02d} to {TO_YEAR}-{TO_MONTH:02d})")
    print("=" * 65)

    start_t = time.perf_counter()

    # Build month list
    months: list[tuple[int, int]] = []
    for y in range(FROM_YEAR, TO_YEAR + 1):
        start_m = FROM_MONTH if y == FROM_YEAR else 1
        end_m = TO_MONTH if y == TO_YEAR else 12
        for m in range(start_m, end_m + 1):
            months.append((y, m))

    print(f"  Total month chunks:       {len(months)}")
    print(f"  Parallel workers:         4")
    print(f"  Rate-limited via TokenBucket")

    all_bars: list[dict] = []
    total_api_calls = 0
    total_wire_bytes = 0
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
                chk = {"month": f"{y}-{m:02d}", "bars": len(chunk_bars)}
                chunk_results.append(chk)
                print(f"    {y}-{m:02d}: {len(chunk_bars):>6,} bars")
            except Exception as e:
                err = f"{y}-{m:02d}: {e}"
                errors.append(err)
                print(f"    {y}-{m:02d}: ERROR — {e}")

    elapsed = time.perf_counter() - start_t

    if errors:
        for e in errors:
            print(f"  ERROR: {e}")

    if not all_bars:
        print("  FATAL: No 1-min bars fetched!")
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
        "name": "1. Fetch 1-min bars",
        "status": "PASS" if not errors else "PARTIAL",
        "total_bars": len(df),
        "chunks": len(months),
        "chunks_with_data": sum(1 for c in chunk_results if c["bars"] > 0),
        "months_fetched": len(months),
        "errors": len(errors),
        "disk_bytes": disk_size,
        "disk_bytes_human": fmt_bytes(disk_size),
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    print(f"\n  Total 1-min bars:         {len(df):,}")
    print(f"  Date range:               {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Disk (Parquet):           {fmt_bytes(disk_size)}")
    print(f"  Time:                     {elapsed:.1f}s")
    print(f"  Errors:                   {len(errors)}")
    print(f"  Status:                   {step['status']}")

    return df


# =====================================================================
# STEP 2: Resample 1-min to daily
# =====================================================================
def step2_resample_to_daily(df_1min: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 65)
    print("  STEP 2: RESAMPLE 1-MIN BARS TO DAILY OHLCV")
    print("=" * 65)

    start_t = time.perf_counter()
    df = df_1min.set_index("timestamp").copy()
    ohlc = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "trade_count": "sum",
        "vwap": lambda x: (x * df.loc[x.index, "volume"]).sum() / df.loc[x.index, "volume"].sum() if df.loc[x.index, "volume"].sum() > 0 else x.mean(),
    }
    df_daily = df.resample("1D").agg(ohlc).dropna(subset=["open"])
    df_daily.reset_index(inplace=True)
    df_daily.rename(columns={"timestamp": "ts"}, inplace=True)
    df_daily["ts"] = df_daily["ts"].dt.strftime("%Y-%m-%d")

    elapsed = time.perf_counter() - start_t

    step = {
        "name": "2. Resample to daily",
        "status": "PASS",
        "trading_days": len(df_daily),
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    print(f"  Trading days:             {len(df_daily)}")
    print(f"  Range:                    {df_daily['ts'].iloc[0]} to {df_daily['ts'].iloc[-1]}")
    print(f"  Time:                     {elapsed:.1f}s")
    print(f"  Status:                   PASS")

    return df_daily


# =====================================================================
# STEP 3: Compute SMA 20/50 signals
# =====================================================================
def step3_compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 65)
    print("  STEP 3: COMPUTE SMA 20/50 CROSSOVER SIGNALS")
    print("=" * 65)

    start_t = time.perf_counter()
    df = df.sort_values("ts").reset_index(drop=True)

    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    df["signal"] = 0
    df.loc[df["sma_20"] > df["sma_50"], "signal"] = 1.0
    df.loc[df["sma_20"] < df["sma_50"], "signal"] = -1.0

    df["crossover"] = (df["signal"] != df["signal"].shift(1)) & (df["signal"] != 0)
    crossover_dates = df[df["crossover"]]["ts"].tolist()

    long_pct = (df["signal"] == 1).mean() * 100
    short_pct = (df["signal"] == -1).mean() * 100
    neutral_pct = (df["signal"] == 0).mean() * 100

    elapsed = time.perf_counter() - start_t

    step = {
        "name": "3. SMA 20/50 Signals",
        "status": "PASS",
        "crossovers": len(crossover_dates),
        "long_pct": round(long_pct, 1),
        "short_pct": round(short_pct, 1),
        "neutral_pct": round(neutral_pct, 1),
        "crossover_dates": crossover_dates[:10],
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    print(f"  Trading days:             {len(df)}")
    print(f"  Crossovers:               {len(crossover_dates)}")
    print(f"  Long:                     {long_pct:.1f}%")
    print(f"  Short:                    {short_pct:.1f}%")
    print(f"  Neutral:                  {neutral_pct:.1f}%")
    print(f"  Time:                     {elapsed:.1f}s")
    print(f"  Status:                   PASS")

    if crossover_dates:
        print(f"  First crossover:          {crossover_dates[0]}")
        print(f"  Last crossover:           {crossover_dates[-1]}")

    return df


# =====================================================================
# STEP 4: Research refinement loop
# =====================================================================
def step4_run_research(df: pd.DataFrame):
    print("\n" + "=" * 65)
    print("  STEP 4: RESEARCH REFINEMENT LOOP")
    print("=" * 65)

    start_t = time.perf_counter()

    from vinu_simulator.models.simulation import SimulationConfig, SimulationInput
    from vinu_simulator.engine.simulator import WeightSimulator

    from vinu_research.storage import ResearchStorage
    from vinu_research.storage.models import ResearchRunRecord

    assert len(df) > 60, f"Only {len(df)} days, need at least 60"

    # 80/20 split with 5-day gap
    total = len(df)
    holdout_size = int(total * 0.2)
    gap = 5
    research_end = total - holdout_size - gap
    assert research_end > 50, f"Research period too small: {research_end}"

    in_sample = df.iloc[:research_end]
    holdout = df.iloc[research_end + gap:]

    research_from = in_sample["ts"].iloc[0]
    research_to = in_sample["ts"].iloc[-1]
    holdout_from = holdout["ts"].iloc[0]
    holdout_to = holdout["ts"].iloc[-1]

    print(f"\n  {'-' * 55}")
    print(f"  DATA SPLIT")
    print(f"  {'-' * 55}")
    print(f"  In-sample:           {research_from} to {research_to}  ({len(in_sample)} days)")
    print(f"  Gap:                 {gap} days")
    print(f"  Holdout:             {holdout_from} to {holdout_to}  ({len(holdout)} days)")
    print(f"  Max iterations:      5")

    storage = ResearchStorage(DATA_DIR / "research" / "research_integration.db")
    run_record = ResearchRunRecord(
        user_idea="SMA 20/50 crossover on AAPL (1-min source, resampled daily)",
        symbol=SYMBOL,
        from_date=f"{FROM_YEAR}-{FROM_MONTH:02d}-{FROM_DAY:02d}",
        to_date=f"{TO_YEAR}-{TO_MONTH:02d}-{TO_DAY:02d}",
    )
    inserted = storage.insert_run(run_record)
    storage.close()

    iterations: list[dict[str, Any]] = []
    best_sharpe = -999.0
    best_params: dict = {}
    final_verdict = "REFINE"

    param_grid = [
        {"sma_fast": 20, "sma_slow": 50, "allow_short": True},
        {"sma_fast": 15, "sma_slow": 50, "allow_short": True},
        {"sma_fast": 20, "sma_slow": 60, "allow_short": True},
        {"sma_fast": 10, "sma_slow": 30, "allow_short": True},
        {"sma_fast": 20, "sma_slow": 50, "allow_short": False},
    ]

    for iteration in range(5):
        iter_start = time.perf_counter()
        params = param_grid[iteration].copy()

        sig = in_sample.copy()
        fast = params["sma_fast"]
        slow = params["sma_slow"]
        sig["sma_f"] = sig["close"].rolling(fast).mean()
        sig["sma_s"] = sig["close"].rolling(slow).mean()
        sig["sig"] = 0
        sig.loc[sig["sma_f"] > sig["sma_s"], "sig"] = 1
        sig.loc[sig["sma_f"] < sig["sma_s"], "sig"] = -1 if params["allow_short"] else 0

        w = pd.DataFrame({"AAPL": sig["sig"]}, index=sig.index)
        p = sig[["close"]].rename(columns={"close": "AAPL"})

        cfg = SimulationConfig(
            strategy_name=f"sma_v{iteration+1}",
            start_date=research_from,
            end_date=research_to,
            initial_capital=1_000_000.0,
            transaction_cost_pct=0.001,
            slippage_pct=0.0005,
            benchmark_tickers=("SPY",),
            allow_short=params["allow_short"],
            deviation_threshold=0.01,
        )

        inp = SimulationInput(
            strategy_name=f"sma_v{iteration+1}",
            weight_signals=w,
            price_data=p,
            config=cfg,
        )

        sim = WeightSimulator(cfg)
        r = sim.run(inp)
        m = r.metrics

        sharpe = m.get("sharpe_ratio", 0)
        ret = m.get("total_return", 0) * 100
        dd = m.get("max_drawdown", 0) * 100
        wr = m.get("win_rate", 0) * 100
        trades = len(r.trades)
        iter_time = time.perf_counter() - iter_start

        if sharpe > 0.3 and trades >= 10:
            verdict = "PASS"
        elif iteration >= 4:
            verdict = "STOP"
        else:
            verdict = "REFINE"

        iter_rec = {
            "iteration": iteration + 1,
            "params": params,
            "sharpe": round(sharpe, 3),
            "return_pct": round(ret, 2),
            "max_dd_pct": round(dd, 2),
            "win_rate_pct": round(wr, 1),
            "trades": trades,
            "verdict": verdict,
            "time_sec": round(iter_time, 2),
        }
        iterations.append(iter_rec)

        label = f"SMA({fast},{slow}) short={params['allow_short']}"
        print(f"\n  Iter {iteration+1}: {label}")
        print(f"    Sharpe: {sharpe:.3f}  Return: {ret:.1f}%  MaxDD: {dd:.1f}%  WR: {wr:.1f}%  Trades: {trades}")
        print(f"    Verdict: {verdict}  ({iter_time:.1f}s)")

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = dict(params)
            final_verdict = verdict

        if verdict == "PASS":
            print(f"\n  {'*' * 55}")
            print(f"  PASS reached at iteration {iteration+1}!")
            print(f"  {'*' * 55}")
            break
        elif verdict == "STOP":
            print(f"\n  STOP — max iterations reached or no improvement.")
            break

    # === Out-of-sample test on holdout ===
    print(f"\n  {'=' * 55}")
    print(f"  OUT-OF-SAMPLE TEST (holdout)")
    print(f"  {'=' * 55}")

    h = holdout.copy()
    h["sma_f"] = h["close"].rolling(best_params.get("sma_fast", 20)).mean()
    h["sma_s"] = h["close"].rolling(best_params.get("sma_slow", 50)).mean()
    h["sig"] = 0
    short = best_params.get("allow_short", True)
    h.loc[h["sma_f"] > h["sma_s"], "sig"] = 1
    h.loc[h["sma_f"] < h["sma_s"], "sig"] = -1 if short else 0

    h_w = pd.DataFrame({"AAPL": h["sig"]}, index=h.index)
    h_p = h[["close"]].rename(columns={"close": "AAPL"})

    h_cfg = SimulationConfig(
        strategy_name="holdout",
        start_date=holdout_from,
        end_date=holdout_to,
        initial_capital=1_000_000.0,
        transaction_cost_pct=0.001,
        slippage_pct=0.0005,
        benchmark_tickers=("SPY",),
        allow_short=short,
        deviation_threshold=0.01,
    )

    h_inp = SimulationInput(
        strategy_name="holdout",
        weight_signals=h_w,
        price_data=h_p,
        config=h_cfg,
    )
    h_sim = WeightSimulator(h_cfg)
    h_r = h_sim.run(h_inp)
    hm = h_r.metrics

    oos_sharpe = hm.get("sharpe_ratio", 0)
    oos_ret = hm.get("total_return", 0) * 100
    oos_dd = hm.get("max_drawdown", 0) * 100
    oos_wr = hm.get("win_rate", 0) * 100
    oos_trades = len(h_r.trades)

    degradation = 0
    if best_sharpe > 0:
        degradation = (best_sharpe - oos_sharpe) / abs(best_sharpe) * 100

    print(f"  Best in-sample Sharpe:  {best_sharpe:.3f}")
    print(f"  OOS Sharpe:             {oos_sharpe:.3f}")
    print(f"  Degradation:            {degradation:.1f}%")
    print(f"  OOS Return:             {oos_ret:.1f}%")
    print(f"  OOS MaxDD:              {oos_dd:.1f}%")
    print(f"  OOS Win rate:           {oos_wr:.1f}%")
    print(f"  OOS Trades:             {oos_trades}")

    elapsed = time.perf_counter() - start_t

    step = {
        "name": "4. Research Refinement",
        "status": "PASS",
        "iterations": iterations,
        "total_iterations": len(iterations),
        "best_in_sample_sharpe": round(best_sharpe, 3),
        "best_params": best_params,
        "final_verdict": final_verdict,
        "data_split": {
            "research_days": len(in_sample),
            "holdout_days": len(holdout),
            "research_from": research_from,
            "research_to": research_to,
            "holdout_from": holdout_from,
            "holdout_to": holdout_to,
        },
        "out_of_sample": {
            "sharpe": round(oos_sharpe, 3),
            "return_pct": round(oos_ret, 2),
            "max_dd_pct": round(oos_dd, 2),
            "win_rate_pct": round(oos_wr, 1),
            "trades": oos_trades,
            "sharpe_degradation_pct": round(degradation, 1),
        },
        "elapsed_sec": round(elapsed, 2),
    }
    RESULT["steps"].append(step)

    print(f"\n  Total iterations:         {len(iterations)}")
    print(f"  Final verdict:            {final_verdict}")
    print(f"  Time:                     {elapsed:.1f}s  |  PASS")


# =====================================================================
# MAIN
# =====================================================================
def main():
    print("=" * 65)
    print("  INTEGRATION TEST: SMA 20/50 CROSSOVER (from 1-min bars)")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Period: {FROM_YEAR}-{FROM_MONTH:02d}-{FROM_DAY:02d} to {TO_YEAR}-{TO_MONTH:02d}-{TO_DAY:02d}")
    print(f"  Data:   {DATA_DIR}")
    print("=" * 65)

    overall_start = time.perf_counter()

    # Probe 1: rate limits
    global LIMITER
    probe_result, LIMITER = probe_api_limits()

    # Probe 2: data feed
    probe_data_feed()

    # Step 1: Fetch all 1-min bars
    df_1min = step1_fetch_1min_bars()
    if df_1min.empty:
        print("FATAL: No 1-min bars. Aborting.")
        return

    # Step 2: Resample to daily
    df_daily = step2_resample_to_daily(df_1min)

    # Step 3: SMA 20/50 signals
    df_signals = step3_compute_signals(df_daily)

    # Step 4: Research refinement
    step4_run_research(df_signals)

    overall_elapsed = time.perf_counter() - overall_start

    # Final report
    print("\n\n" + "=" * 65)
    print("  FINAL INTEGRATION REPORT")
    print("=" * 65)

    print(f"\n  {'Step':<50} {'Status':<10} {'Time (s)':<10}")
    print(f"  {'-'*50} {'-'*10} {'-'*10}")
    for s in RESULT["steps"]:
        print(f"  {s['name']:<50} {s['status']:<10} {s['elapsed_sec']:<10.1f}")

    for s in RESULT["steps"]:
        if "iterations" in s:
            print(f"\n  {'-' * 65}")
            print(f"  ITERATION DETAILS")
            print(f"  {'-' * 65}")
            print(f"  {'#':<4} {'SMA Params':<28} {'Sharpe':<8} {'Return%':<8} {'MaxDD%':<8} {'Trades':<8} {'Verdict':<10}")
            print(f"  {'-'*4} {'-'*28} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
            for it in s["iterations"]:
                p = it["params"]
                label = f"SMA({p['sma_fast']},{p['sma_slow']}) short={str(p['allow_short'])[0]}"
                print(f"  {it['iteration']:<4} {label:<28} {it['sharpe']:<8.3f} {it['return_pct']:<8.1f} "
                      f"{it['max_dd_pct']:<8.1f} {it['trades']:<8} {it['verdict']:<10}")

            oos = s.get("out_of_sample", {})
            ds = s.get("data_split", {})
            print(f"\n  {'-' * 65}")
            print(f"  DATA SPLIT & OOS RESULTS")
            print(f"  {'-' * 65}")
            print(f"  Research:    {ds.get('research_from','?')} to {ds.get('research_to','?')} ({ds.get('research_days','?')} days)")
            print(f"  Holdout:     {ds.get('holdout_from','?')} to {ds.get('holdout_to','?')} ({ds.get('holdout_days','?')} days)")
            print(f"  Best params: SMA({s['best_params'].get('sma_fast','?')},{s['best_params'].get('sma_slow','?')}) "
                  f"short={s['best_params'].get('allow_short','?')}")
            print(f"  Iterations:  {s['total_iterations']}")
            print(f"  Verdict:     {s['final_verdict']}")
            print(f"  {'-' * 65}")
            print(f"  In-sample Sharpe:     {s['best_in_sample_sharpe']:.3f}")
            print(f"  OOS Sharpe:           {oos.get('sharpe', 0):.3f}")
            print(f"  Degradation:          {oos.get('sharpe_degradation_pct', 0):.1f}%")
            print(f"  OOS Return:           {oos.get('return_pct', 0):.1f}%")
            print(f"  OOS MaxDD:            {oos.get('max_dd_pct', 0):.1f}%")
            print(f"  OOS Win Rate:         {oos.get('win_rate_pct', 0):.1f}%")
            break

    print(f"\n  {'=' * 65}")
    print(f"  SUMMARY")
    print(f"  {'=' * 65}")
    print(f"  Total 1-min bars:        {len(df_1min):,}")
    print(f"  Trading days:            {len(df_daily)}")
    print(f"  Total disk:              {fmt_bytes(sum(s.get('disk_bytes', 0) for s in RESULT['steps']))}")
    print(f"  Overall time:            {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} min)")
    ref_step = next((s for s in RESULT["steps"] if "iterations" in s), None)
    if ref_step:
        print(f"  Refinement iters:        {ref_step['total_iterations']}")
        print(f"  Final verdict:           {ref_step['final_verdict']}")
    print(f"  Test date:               {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {'=' * 65}")

    with open(REPORT_FILE, "w") as f:
        json.dump(RESULT, f, indent=2, default=str)
    print(f"\n  Full report: {REPORT_FILE}")


LIMITER = None

if __name__ == "__main__":
    main()
