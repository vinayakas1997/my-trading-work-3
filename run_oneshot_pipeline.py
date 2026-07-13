#!/usr/bin/env python3
"""One-shot pipeline: 3 stocks, no LLM, CPU monitoring, all strategies.

Run: python -u run_oneshot_pipeline.py
"""

import os, sys, time, json, shutil, subprocess, threading, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timedelta

STOCKS = ["AAPL", "TSLA", "NVDA"]
STRATEGIES = ["ma_crossover", "rsi_mean_reversion", "news_aware_momentum"]
SERVICES = ["news-api", "stock-api", "features-api", "correlation-api", "strategy-api", "simulator-api"]
COMPOSE_FILE = "vinu-components/docker-compose.oneshot.yml"
DATA_DIR = Path("./oneshot_data")
SEED_SCRIPT = DATA_DIR / "stock" / "_seed.py"

class C:
    HDR = '\033[95m'; OK = '\033[94m'; GRN = '\033[92m'
    WARN = '\033[93m'; FAIL = '\033[91m'; END = '\033[0m'; BLD = '\033[1m'

def log(msg): print(msg, flush=True)
def info(msg): log(f"{C.OK}[INFO]{C.END} {msg}")
def ok(msg):   log(f"{C.GRN}[OK]{C.END} {C.BLD}{msg}{C.END}")
def warn(msg): log(f"{C.WARN}[WARN]{C.END} {msg}")
def fail(msg): log(f"{C.FAIL}[FAIL]{C.END} {C.BLD}{msg}{C.END}")

def run(args, capture=True, check=True, timeout=120):
    try:
        r = subprocess.run(args, capture_output=capture, text=True, timeout=timeout)
        if check and r.returncode != 0:
            fail(f"Command failed: {' '.join(args)}")
            if capture: log(r.stderr[:2000])
            return None
        return r
    except subprocess.TimeoutExpired:
        fail(f"Timed out: {' '.join(args)}")
        return None

# ---- CPU Monitor ----
resource_stats = {s: {"cpu": [], "mem": []} for s in SERVICES}
profiling_active = True

def profiling_loop():
    global profiling_active
    while profiling_active:
        r = subprocess.run(["docker", "stats", "--no-stream", "--format",
                          "{{.Name}},{{.CPUPerc}},{{.MemUsage}}"],
                          capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().split("\n"):
            if not line: continue
            parts = line.split(",")
            if len(parts) < 3: continue
            name, cpu_str, mem_str = parts[0], parts[1], parts[2]
            name_clean = name.replace("/", "").strip()
            svc = next((s for s in SERVICES if s in name_clean), None)
            if not svc: continue
            try:
                cv = float(cpu_str.replace("%", "").strip())
                mu = mem_str.split("/")[0].strip()
                if "GiB" in mu: mv = float(mu.replace("GiB", "").strip()) * 1024
                elif "MiB" in mu: mv = float(mu.replace("MiB", "").strip())
                elif "KiB" in mu: mv = float(mu.replace("KiB", "").strip()) / 1024
                else: mv = float(mu.replace("B", "").strip()) / (1024 * 1024)
                resource_stats[svc]["cpu"].append(cv)
                resource_stats[svc]["mem"].append(mv)
            except: pass
        time.sleep(1)

def http_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"GET {url}: {e}")

def http_post(url, body, timeout=30):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"POST {url} ({e.code}): {e.read().decode()[:500]}")
    except Exception as e:
        raise RuntimeError(f"POST {url}: {e}")

def docker_exec(service, cmd_list, check=True, timeout=120):
    full = ["docker", "compose", "-f", COMPOSE_FILE, "exec", "-T", service] + cmd_list
    return run(full, check=check, timeout=timeout)

# ---- Seed script ----
def write_seed_script():
    SEED_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    SEED_SCRIPT.write_text("\n".join([
        'import sqlite3, pyarrow as pa, pyarrow.parquet as pq, time, os',
        'conn = sqlite3.connect("/data/meta.db")',
        'conn.execute("PRAGMA journal_mode=WAL")',
        'conn.execute("PRAGMA busy_timeout=30000")',
        'conn.execute("CREATE TABLE IF NOT EXISTS symbol_catalog (symbol TEXT PRIMARY KEY, provider TEXT, first_bar_ts INTEGER, last_bar_ts INTEGER, archive_through TEXT, live_file TEXT, backfill_status TEXT, updated_at INTEGER, has_adj_data INTEGER, gap_count INTEGER, last_validation_at INTEGER)")',
        'conn.execute("CREATE TABLE IF NOT EXISTS watchlist_tickers (ticker TEXT PRIMARY KEY, added_at INTEGER)")',
        'conn.execute("CREATE TABLE IF NOT EXISTS vinu_settings (key TEXT PRIMARY KEY, value TEXT)")',
        'now_ts = int(time.time())',
        'base_ts = now_ts - 90 * 86400',
        'conn.execute("INSERT OR REPLACE INTO vinu_settings VALUES (\'poll_interval_sec\',\'60\')")',
        'conn.execute("INSERT OR REPLACE INTO vinu_settings VALUES (\'default_provider\',\'test\')")',
        'conn.execute("INSERT OR REPLACE INTO vinu_settings VALUES (\'data_root\',\'/data\')")',
        'symbols = ["AAPL", "TSLA", "NVDA"]',
        'for sym in symbols:',
        '    conn.execute("INSERT OR REPLACE INTO symbol_catalog VALUES (?,?,?,?,?,?,?,?,?,?,?)", (sym, "test", base_ts, now_ts, None, None, "complete", now_ts, 0, 0, now_ts))',
        '    conn.execute("INSERT OR REPLACE INTO watchlist_tickers VALUES (?,?)", (sym, now_ts))',
        'conn.commit()',
        'for sym in symbols:',
        '    bars = []',
        '    for i in range(92):',
        '        bar_ts = base_ts + i * 86400',
        '        cp = 100.0 + i * 0.5 + (1.5 if i % 3 == 0 else -0.5) + (hash(sym) % 20 - 10)',
        '        bars.append({"symbol": sym, "provider": "test", "bar_ts": int(bar_ts), "open": float(cp-0.5), "high": float(cp+1.2), "low": float(cp-1.2), "close": float(cp), "volume": 1500000.0, "vwap": float(cp), "trades": 120, "adj_factor": 1.0})',
        '    fields = [("symbol", pa.string()), ("provider", pa.string()), ("bar_ts", pa.int64()), ("open", pa.float64()), ("high", pa.float64()), ("low", pa.float64()), ("close", pa.float64()), ("volume", pa.float64()), ("vwap", pa.float64()), ("trades", pa.int64()), ("adj_factor", pa.float64())]',
        '    schema = pa.schema(fields)',
        '    table = pa.Table.from_pylist(bars, schema=schema)',
        '    pdir = os.path.join("/data", "prices", "1m", sym, "archive")',
        '    os.makedirs(pdir, exist_ok=True)',
        '    pq.write_table(table, os.path.join(pdir, "2026.parquet"))',
        '    print(f"Seeded {sym}: {len(bars)} bars")',
        'conn.close()',
        'print("STOCK_SEED_OK")',
    ]))

# ---- Main ----
def main():
    global profiling_active
    step_times = {}

    log(f"\n{C.HDR}{'='*70}{C.END}")
    log(f"{C.HDR}  ONESHOT PIPELINE — 3 Stocks, No LLM, CPU Monitoring{C.END}")
    log(f"{C.HDR}{'='*70}{C.END}\n")

    # Step 0: Cleanup
    info("Cleaning up previous data...")
    run(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"], check=False)
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    for d in ["shared", "news", "stock", "features", "correlation", "strategy", "simulator"]:
        (DATA_DIR / d).mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "shared" / "watchlist.json").write_text(json.dumps({"tickers": STOCKS}))
    write_seed_script()
    ok(f"Watchlist seeded: {STOCKS}")

    # Step 1: Build & Start
    t = time.time()
    info("Building and launching Docker Compose stack...")
    r = run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--build"], timeout=300)
    if r is None: sys.exit(1)
    step_times["Build & Startup"] = time.time() - t
    ok("Containers started")

    # Resolve container IDs
    for svc in SERVICES:
        r2 = subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "ps", "-q", svc],
                           capture_output=True, text=True)
        info(f"  {svc} -> {(r2.stdout.strip()[:12]) if r2.stdout.strip() else 'N/A'}")

    # Start profiling
    threading.Thread(target=profiling_loop, daemon=True).start()
    info("CPU profiling started")

    # Step 2: Wait for APIs
    t = time.time()
    info("Waiting for HTTP APIs...")
    for name, url in {
        "news-api": "http://localhost:8080/settings",
        "stock-api": "http://localhost:8081/settings",
        "features-api": "http://localhost:8082/presets",
        "correlation-api": "http://localhost:8083/settings",
        "strategy-api": "http://localhost:8084/strategies",
        "simulator-api": "http://localhost:8085/health",
    }.items():
        for attempt in range(45):
            try:
                http_get(url)
                ok(f"  {name} READY")
                break
            except:
                time.sleep(2)
        else:
            fail(f"{name} not ready!")
            sys.exit(1)
    step_times["API Readiness"] = time.time() - t

    # Step 3: Sync watchlists
    info("Syncing watchlists...")
    try:
        http_post("http://localhost:8081/watchlist/sync", {})
        http_post("http://localhost:8080/watchlist/sync", {})
        ok("Watchlists synced")
    except Exception as e:
        warn(f"Watchlist sync: {e}")

    # Step 4: Seed stock data
    t = time.time()
    info("Seeding stock price data...")
    r = docker_exec("stock-api", ["python", "/data/_seed.py"], timeout=60)
    if r is None or r.returncode != 0:
        fail("Stock seed failed!"); sys.exit(1)
    time.sleep(2)
    # Verify
    for sym in STOCKS:
        d = json.loads(http_get(f"http://localhost:8081/candles/{sym}?days=90&limit=5"))
        info(f"  {sym}: {d['count']} candles")
    ok("Stock data verified")
    step_times["Stock Seed & Verify"] = time.time() - t

    # Step 5: News ingest (one-shot, no LLM)
    t = time.time()
    info("Running news ingest (one-shot, LLM disabled)...")
    docker_exec("news-api", ["vinu-news-ingest", "--once"], check=False, timeout=120)
    for sym in STOCKS:
        try:
            d = json.loads(http_get(f"http://localhost:8080/ticker/{sym}?days=90&limit=10"))
            info(f"  {sym}: {len(d) if isinstance(d, list) else d.get('count',0)} articles")
        except:
            info(f"  {sym}: no news articles found")
    step_times["News Ingest"] = time.time() - t
    ok("News ingest done")

    # Step 6: Features computation
    t = time.time()
    info("Computing features...")
    docker_exec("features-api", ["vinu-features", "submit",
                "--title", "pipeline_run",
                "--symbols", ",".join(STOCKS),
                "--days", "90", "--interval", "1d",
                "--preset", "full_ta", "--run"],
                check=False, timeout=60)
    docker_exec("features-api", ["vinu-features", "worker", "--once"],
                check=False, timeout=120)
    step_times["Features Compute"] = time.time() - t
    ok("Features computed")

    # Step 7: Correlation compute
    t = time.time()
    info("Computing correlations...")
    docker_exec("correlation-api", ["vinu-correlation-compute"] + STOCKS,
                check=False, timeout=120)
    step_times["Correlation Compute"] = time.time() - t
    ok("Correlation computed")

    # Step 8: Strategy evaluation
    t = time.time()
    info("Evaluating strategies...")
    strat_results = {}
    for name in STRATEGIES:
        try:
            result = http_post(f"http://localhost:8084/strategies/{name}/evaluate?symbols={'&symbols='.join(STOCKS)}", {})
            strat_results[name] = result
            ws = result.get("weights", [])
            total = sum(w.get("weight", 0) for w in ws)
            info(f"  {name}: {len(ws)} weights, sum={total:.4f}, run_id={result.get('run_id','?')}")
        except Exception as e:
            fail(f"  {name}: {e}")
    step_times["Strategy Evaluation"] = time.time() - t

    # Step 9: Simulator backtest
    t = time.time()
    info("Running backtests...")
    end_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    sim_results = {}
    for name in STRATEGIES:
        try:
            result = http_post("http://localhost:8085/simulate", {
                "strategy_name": name,
                "start_date": start_str,
                "end_date": end_str,
                "initial_capital": 100000.0,
                "transaction_cost_pct": 0.001,
                "slippage_pct": 0.0005,
                "benchmark_tickers": STOCKS[:1],
                "allow_short": True,
            })
            sim_results[name] = result
            m = result.get("metrics", {})
            info(f"  {name}: trades={result.get('trade_count')}, "
                 f"sharpe={m.get('sharpe_ratio',0):.4f}, "
                 f"return={m.get('total_return',0):.4f}")
        except Exception as e:
            fail(f"  {name}: {e}")
    step_times["Simulator Backtest"] = time.time() - t

    ok("\nAll pipeline steps completed!")

    # Stop profiling
    profiling_active = False
    time.sleep(2)

    # Build report
    report = {
        "timestamp": datetime.now().isoformat(),
        "stocks": STOCKS,
        "strategies": STRATEGIES,
        "llm_involved": False,
        "pipeline_timing_sec": {k: round(v, 2) for k, v in step_times.items()},
        "peak_cpu": {},
        "peak_mem_mib": {},
        "strategy_results": {},
        "simulator_results": {},
    }
    for svc in SERVICES:
        c = resource_stats[svc]["cpu"]
        m = resource_stats[svc]["mem"]
        report["peak_cpu"][svc] = round(max(c), 1) if c else 0.0
        report["peak_mem_mib"][svc] = round(max(m), 1) if m else 0.0

    for name, r in strat_results.items():
        report["strategy_results"][name] = {
            "run_id": r.get("run_id", ""),
            "weights": [{"symbol": w["symbol"], "weight": round(w["weight"], 4)}
                        for w in r.get("weights", [])]
        }
    for name, r in sim_results.items():
        m = r.get("metrics", {})
        report["simulator_results"][name] = {
            "run_id": r.get("run_id", ""),
            "trade_count": r.get("trade_count", 0),
            "sharpe": round(m.get("sharpe_ratio", 0), 4),
            "total_return": round(m.get("total_return", 0), 4),
            "max_drawdown": round(m.get("max_drawdown", 0), 4),
        }

    (DATA_DIR / "cpu_report.json").write_text(json.dumps(report, indent=2))
    ok(f"Report saved to {DATA_DIR / 'cpu_report.json'}")

    # Print summary
    log(f"\n{C.HDR}{'='*70}{C.END}")
    log(f"{C.HDR}  PERFORMANCE REPORT{C.END}")
    log(f"{C.HDR}{'='*70}{C.END}")
    log("")
    log(f"{C.BLD}{'Step':<30} {'Time':<12}{C.END}")
    log("-" * 45)
    for s, d in step_times.items():
        log(f"{s:<30} {d:.2f}s")
    log()
    log(f"{C.BLD}{'Service':<25} {'Peak CPU%':<12} {'Peak RAM (MiB)':<16}{C.END}")
    log("-" * 55)
    for svc in SERVICES:
        log(f"{svc:<25} {report['peak_cpu'].get(svc, 0):>8.1f}%   "
            f"{report['peak_mem_mib'].get(svc, 0):>10.1f} MiB")
    log()
    for name in STRATEGIES:
        sr = report["strategy_results"].get(name, {})
        if sr.get("weights"):
            log(f"{C.BLD}{name} weights:{C.END}")
            for w in sr["weights"]:
                log(f"  {w['symbol']:<8} weight={w['weight']:.4f}")
    log()
    for name in STRATEGIES:
        sr = report["simulator_results"].get(name, {})
        if sr:
            log(f"{C.BLD}{name} backtest:{C.END}")
            log(f"  Trades={sr['trade_count']}  Sharpe={sr['sharpe']:.4f}  "
                f"Return={sr['total_return']:.4f}  MaxDD={sr['max_drawdown']:.4f}")

    # Tear down
    info("Tearing down containers...")
    run(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"], check=False)
    ok("Done! All containers stopped.")

if __name__ == "__main__":
    main()
