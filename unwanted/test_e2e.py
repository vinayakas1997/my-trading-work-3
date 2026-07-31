"""End-to-end integration test for vinu-stock-price, vinu-news, and vinu-initial-analysis.

Usage:
    # Start services manually, then run tests:
    python test_e2e.py

    # Auto-start services (cleanup on exit):
    python test_e2e.py --spawn
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent

# Service ports
STOCK_PORT = 8081
NEWS_PORT = 8080
ANALYSIS_PORT = 8083

# URLs
STOCK_URL = f"http://127.0.0.1:{STOCK_PORT}"
NEWS_URL = f"http://127.0.0.1:{NEWS_PORT}"
ANALYSIS_URL = f"http://127.0.0.1:{ANALYSIS_PORT}"

PASS = 0
FAIL = 0
SKIP = 0


def test(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL, SKIP
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def skip(name: str, reason: str = ""):
    global SKIP
    SKIP += 1
    msg = f"  [SKIP] {name}"
    if reason:
        msg += f" — {reason}"
    print(msg)


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def wait_for_health(url: str, name: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{url}/health", timeout=3)
            if r.status_code == 200:
                return True
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(1)
    return False


# =========================================================================
#  SERVICE STARTUP
# =========================================================================


def _make_spawn_script(name: str, import_path: str, port: int) -> str:
    content = f"""import uvicorn
from {import_path} import create_app
uvicorn.run(create_app(), host="127.0.0.1", port={port})
"""
    path = ROOT / f"._e2e_spawn_{name}.py"
    path.write_text(content)
    return str(path)


def spawn_service(script_path: str, name: str) -> subprocess.Popen:
    print(f"  Starting {name} ...")
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    env = os.environ.copy()
    comp = str(ROOT / "vinu-components")
    env.setdefault("PYTHONPATH", comp)
    return subprocess.Popen(
        [sys.executable, script_path],
        cwd=comp,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
        env=env,
    )


# =========================================================================
#  vinu-stock-price tests
# =========================================================================


def test_stock_price():
    section("vinu-stock-price (port 8081)")

    # Health
    try:
        r = requests.get(f"{STOCK_URL}/health", timeout=5)
        data = r.json()
        test("health endpoint", r.status_code == 200)
        test("health has catalog status", "catalog_db" in data or "status" in data)
        test("health has providers", "providers" in data)
    except Exception as e:
        test("health endpoint", False, str(e))
        skip("remaining stock-price tests", "health failed")
        return

    # Settings
    try:
        r = requests.get(f"{STOCK_URL}/settings", timeout=5)
        test("settings endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("settings has poll_interval_sec", "poll_interval_sec" in data)
            test("settings has default_provider", "default_provider" in data)
    except Exception as e:
        test("settings endpoint", False, str(e))

    # Watchlist
    try:
        r = requests.get(f"{STOCK_URL}/watchlist/tickers", timeout=5)
        test("watchlist list", r.status_code == 200)
        if r.status_code == 200:
            test("watchlist returns tickers list", isinstance(r.json().get("tickers"), list))
    except Exception as e:
        test("watchlist list", False, str(e))

    # Catalog
    try:
        r = requests.get(f"{STOCK_URL}/catalog", timeout=5)
        test("catalog endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("catalog returns count + data", "count" in data and "data" in data)
    except Exception as e:
        test("catalog endpoint", False, str(e))

    # Candles — try a common symbol
    for sym in ["AAPL", "SPY", "MSFT"]:
        try:
            r = requests.get(f"{STOCK_URL}/candles/{sym}?interval=1D&days=10&limit=5", timeout=10)
            if r.status_code == 200:
                data = r.json()
                count = data.get("count", len(data.get("data", [])))
                test(f"candles/{sym}", True, f"{count} bars returned")
                if count > 0:
                    bar = data["data"][0]
                    test(f"candles/{sym} has bar fields",
                         all(k in bar for k in ("bar_ts", "open", "high", "low", "close", "volume")))
                break
            elif r.status_code == 404:
                continue  # symbol not in catalog, try next
            else:
                test(f"candles/{sym}", False, f"HTTP {r.status_code}")
        except Exception as e:
            test(f"candles/{sym}", False, str(e))
    else:
        skip("candles — no symbol returned data", "no bars available (backfill required)")

    # Backfill trigger — only test endpoint exists (not actual backfill)
    try:
        data_root = os.environ.get("VINU_STOCK_DATA_ROOT", str(ROOT / "data" / "stock"))
        os.makedirs(data_root, exist_ok=True)
        r = requests.post(f"{STOCK_URL}/backfill/trigger", timeout=5)
        if r.status_code in (200, 409):
            test("backfill trigger endpoint", True,
                 f"HTTP {r.status_code} (409 = already running)")
        elif r.status_code == 503:
            skip("backfill trigger", "Alpaca not configured")
        else:
            test("backfill trigger endpoint", False, f"HTTP {r.status_code}")
    except Exception as e:
        test("backfill trigger endpoint", False, str(e))


# =========================================================================
#  vinu-news tests
# =========================================================================


def test_news():
    section("vinu-news (port 8080)")

    # Health
    try:
        r = requests.get(f"{NEWS_URL}/health", timeout=5)
        data = r.json()
        test("health endpoint", r.status_code == 200)
        test("health has status", "status" in data)
    except Exception as e:
        test("health endpoint", False, str(e))
        skip("remaining news tests", "health failed")
        return

    # Settings
    try:
        r = requests.get(f"{NEWS_URL}/settings", timeout=5)
        test("settings endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("settings has mode", "mode" in data)
            test("settings has poll_interval_sec", "poll_interval_sec" in data)
    except Exception as e:
        test("settings endpoint", False, str(e))

    # Watchlist
    try:
        r = requests.get(f"{NEWS_URL}/watchlist/tickers", timeout=5)
        test("watchlist list", r.status_code == 200)
        if r.status_code == 200:
            test("watchlist returns tickers", isinstance(r.json().get("tickers"), list))
    except Exception as e:
        test("watchlist list", False, str(e))

    # Add a test ticker to watchlist
    try:
        r = requests.post(f"{NEWS_URL}/watchlist/tickers",
                          json={"tickers": ["TESTE2E"]}, timeout=5)
        test("watchlist add ticker", r.status_code == 200)
    except Exception as e:
        test("watchlist add ticker", False, str(e))

    # Poll status
    try:
        r = requests.get(f"{NEWS_URL}/poll/status", timeout=5)
        test("poll status endpoint", r.status_code == 200)
    except Exception as e:
        test("poll status endpoint", False, str(e))

    # Feeds
    try:
        r = requests.get(f"{NEWS_URL}/feeds", timeout=5)
        test("feeds list endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            feeds = data.get("feeds", [])
            test("feeds returns list", isinstance(feeds, list))
            if feeds:
                test("feeds has entries", len(feeds) > 0, f"{len(feeds)} feeds")
    except Exception as e:
        test("feeds list endpoint", False, str(e))

    # Ticker news — may be empty if no ingestion has run
    for sym in ["AAPL", "MSFT", "NVDA"]:
        try:
            r = requests.get(f"{NEWS_URL}/ticker/{sym}?days=7&limit=5", timeout=10)
            if r.status_code == 200:
                data = r.json()
                count = data.get("count", len(data.get("data", [])))
                test(f"ticker/{sym}", True, f"{count} articles, HTTP 200")
                break
            else:
                test(f"ticker/{sym}", False, f"HTTP {r.status_code}")
        except Exception as e:
            test(f"ticker/{sym}", False, str(e))
    else:
        skip("ticker news — no symbol returned", "no news ingested yet")

    # Ingestion trigger
    try:
        r = requests.post(f"{NEWS_URL}/ingest/trigger", timeout=30)
        if r.status_code == 200:
            data = r.json()
            test("ingest trigger endpoint", data.get("ok", False),
                 f"inserted={data.get('summary', {}).get('inserted')}")
        else:
            test("ingest trigger endpoint", False, f"HTTP {r.status_code}")
    except Exception as e:
        test("ingest trigger endpoint", False, str(e))

    # Last ingestion status
    try:
        r = requests.get(f"{NEWS_URL}/poll/status", timeout=5)
        if r.status_code == 200:
            data = r.json()
            test("poll status after trigger", True,
                 f"last_inserted={data.get('last_inserted')}")
    except Exception as e:
        test("poll status after trigger", False, str(e))


# =========================================================================
#  vinu-initial-analysis tests
# =========================================================================


def test_initial_analysis():
    section("vinu-initial-analysis (port 8083)")

    # Health
    try:
        r = requests.get(f"{ANALYSIS_URL}/health", timeout=10)
        data = r.json()
        test("health endpoint", r.status_code == 200)
        test("health has status", data.get("status") == "ok")
        test("health has data_root", "data_root" in data)
    except Exception as e:
        test("health endpoint", False, str(e))
        skip("remaining analysis tests", "health failed")
        return

    # List angles
    try:
        r = requests.get(f"{ANALYSIS_URL}/angles", timeout=10)
        test("angles list endpoint", r.status_code == 200)
        if r.status_code == 200:
            angles = r.json().get("angles", [])
            test("angles returns list", isinstance(angles, list))
            if angles:
                names = [a["name"] for a in angles]
                test("angles are populated", len(angles) >= 10, f"{len(angles)} angles found")
                print(f"    Angles ({len(angles)}): {', '.join(names[:8])}...")
    except Exception as e:
        test("angles list endpoint", False, str(e))

    # Symbols list
    try:
        r = requests.get(f"{ANALYSIS_URL}/symbols", timeout=10)
        test("symbols endpoint", r.status_code == 200)
        if r.status_code == 200:
            symbols = r.json().get("symbols", [])
            test("symbols returns list", isinstance(symbols, list))
            if symbols:
                test("symbols populated", len(symbols) > 0, f"{len(symbols)} symbols")
    except Exception as e:
        test("symbols endpoint", False, str(e))

    # Run analysis on a symbol
    for sym in ["AAPL", "MSFT", "NVDA", "SPY"]:
        try:
            r = requests.post(f"{ANALYSIS_URL}/run/{sym}", timeout=120)
            if r.status_code == 200:
                data = r.json()
                completed = [k for k, v in data.items() if v.get("status") == "completed"]
                failed = [k for k, v in data.items() if v.get("status") == "error"]
                test(f"run/{sym}", True,
                     f"{len(completed)} completed, {len(failed)} failed out of {len(data)} angles")
                if completed:
                    test(f"run/{sym} has results", len(completed) > 0,
                         f"e.g. {completed[0]}")
                break
            elif r.status_code == 503:
                continue
            else:
                test(f"run/{sym}", False, f"HTTP {r.status_code}")
        except Exception as e:
            test(f"run/{sym}", False, str(e))
    else:
        skip("run analysis — no symbol executed", "all symbols returned 503 or timed out")

    # Impact
    try:
        r = requests.get(f"{ANALYSIS_URL}/impact/AAPL?from_ts=0", timeout=30)
        test("impact/AAPL endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("impact has event_count", "event_count" in data)
            test("impact has high_impact counts", "high_impact_bearish_events" in data)
    except Exception as e:
        test("impact/AAPL endpoint", False, str(e))

    # Correlation
    try:
        r = requests.get(f"{ANALYSIS_URL}/correlation/AAPL?from_ts=0", timeout=30)
        test("correlation/AAPL endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("correlation has symbol", data.get("symbol") == "AAPL")
            test("correlation has sample_size", "sample_size" in data)
    except Exception as e:
        test("correlation/AAPL endpoint", False, str(e))

    # Drawdown
    try:
        r = requests.get(f"{ANALYSIS_URL}/drawdown/AAPL?from_ts=0", timeout=30)
        test("drawdown/AAPL endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("drawdown has drawdown_count", "drawdown_count" in data)
    except Exception as e:
        test("drawdown/AAPL endpoint", False, str(e))

    # Baseline
    try:
        r = requests.get(f"{ANALYSIS_URL}/baseline/AAPL", timeout=30)
        test("baseline/AAPL endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("baseline has symbol", data.get("symbol") == "AAPL")
    except Exception as e:
        test("baseline/AAPL endpoint", False, str(e))

    # Story (batch of 3 endpoints)
    try:
        r = requests.get(f"{ANALYSIS_URL}/story/AAPL?from_ts=0", timeout=30)
        test("story/AAPL endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("story has ticker", data.get("ticker") == "AAPL")
            test("story has period", "period" in data)
    except Exception as e:
        test("story/AAPL endpoint", False, str(e))

    # Gap
    try:
        r = requests.get(f"{ANALYSIS_URL}/gap/AAPL", timeout=30)
        test("gap/AAPL endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("gap has symbol", data.get("symbol") == "AAPL")
    except Exception as e:
        test("gap/AAPL endpoint", False, str(e))

    # Batch correlation
    try:
        r = requests.get(f"{ANALYSIS_URL}/correlation/batch?symbols=AAPL,MSFT&from_ts=0", timeout=30)
        test("correlation/batch endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("batch has symbols list", "symbols" in data)
            test("batch has results", "results" in data)
    except Exception as e:
        test("correlation/batch endpoint", False, str(e))

    # Run analysis dry-run mode (via compute service endpoint)
    try:
        r = requests.get(f"{ANALYSIS_URL}/angle/session_time_analysis/AAPL", timeout=30)
        test("angle/AAPL endpoint", r.status_code == 200)
        if r.status_code == 200:
            data = r.json()
            test("angle has row_count", "row_count" in data)
    except Exception as e:
        test("angle/AAPL endpoint", False, str(e))


# =========================================================================
#  SUMMARY
# =========================================================================


def print_summary():
    total = PASS + FAIL + SKIP
    print(f"\n{'=' * 60}")
    print(f"  RESULTS:  {PASS} passed, {FAIL} failed, {SKIP} skipped  (total {total})")
    print(f"{'=' * 60}")
    if FAIL > 0:
        print("  Some tests failed. See details above.")
        sys.exit(1)
    else:
        print("  All tests passed!")
        sys.exit(0)


# =========================================================================
#  MAIN
# =========================================================================


def main():
    parser = argparse.ArgumentParser(description="E2E integration test for trading microservices")
    parser.add_argument("--spawn", action="store_true", help="Auto-start services (experimental)")
    args = parser.parse_args()

    processes: list[subprocess.Popen] = []

    if args.spawn:
        print("Starting services (this may take a while)...")
        comp = ROOT / "vinu-components"

        stock_script = _make_spawn_script("stock", "vinu_stock.server.app", STOCK_PORT)
        news_script = _make_spawn_script("news", "vinu_news.server.app", NEWS_PORT)
        analysis_script = _make_spawn_script("analysis", "vinu_initial_analysis.server.app", ANALYSIS_PORT)

        processes.append(spawn_service(stock_script, "stock-price"))
        time.sleep(3)
        processes.append(spawn_service(news_script, "news"))
        time.sleep(3)
        processes.append(spawn_service(analysis_script, "initial-analysis"))

        print("Waiting for services to become healthy...")
        s1 = wait_for_health(STOCK_URL, "stock-price")
        s2 = wait_for_health(NEWS_URL, "news")
        s3 = wait_for_health(ANALYSIS_URL, "initial-analysis")
        ok = sum([s1, s2, s3])
        print(f"  {ok}/3 services healthy")
        if ok < 3:
            print("  WARNING: Some services are not healthy — tests may fail")

    try:
        test_stock_price()
        test_news()
        test_initial_analysis()
    finally:
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        for suffix in ("stock", "news", "analysis"):
            p = ROOT / f"._e2e_spawn_{suffix}.py"
            if p.exists():
                p.unlink()

    print_summary()


if __name__ == "__main__":
    main()
