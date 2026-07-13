#!/usr/bin/env python3
import os
import sys
import time
import json
import shutil
import subprocess
import threading
from pathlib import Path
import urllib.request
import urllib.error
from datetime import datetime, timedelta

# Config
SERVICES = [
    "news-ingest", "news-api",
    "stock-ingest", "stock-api",
    "features-worker", "features-api",
    "correlation-compute", "correlation-api",
    "strategy-api", "simulator-api"
]

DATA_DIR = Path("./integration_test_data")
COMPOSE_FILE = "vinu-components/docker-compose.integration.yml"

# Colors for beautiful terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_info(msg):
    print(f"{Colors.OKBLUE}[INFO]{Colors.ENDC} {msg}")

def log_success(msg):
    print(f"{Colors.OKGREEN}[SUCCESS]{Colors.ENDC} {Colors.BOLD}{msg}{Colors.ENDC}")

def log_warning(msg):
    print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {msg}")

def log_fail(msg):
    print(f"{Colors.FAIL}[FAIL]{Colors.ENDC} {Colors.BOLD}{msg}{Colors.ENDC}")

# Helper to run shell commands
def run_cmd(args, capture=False, check=True):
    res = subprocess.run(args, capture_output=capture, text=True)
    if check and res.returncode != 0:
        log_fail(f"Command {' '.join(args)} failed with exit code {res.returncode}")
        if capture:
            print(res.stderr)
        sys.exit(res.returncode)
    return res

# Thread-safe dictionary to keep track of resource stats
resource_stats = {svc: {"cpu": [], "mem": [], "oom": False} for svc in SERVICES}
profiling_active = True

def profiling_loop(container_ids):
    global profiling_active
    while profiling_active:
        for svc, cid in container_ids.items():
            if not cid:
                continue
            # Query docker stats for CPU % and Memory Usage
            # Format: CPU %, Mem Usage / Limit
            res = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}},{{.MemUsage}}", cid],
                capture_output=True, text=True
            )
            out = res.stdout.strip()
            if out:
                try:
                    cpu_str, mem_str = out.split(",")
                    cpu_val = float(cpu_str.replace("%", "").strip())
                    
                    # Parse mem_str (e.g., "12.5MiB / 15.6GiB" or "500KiB / 15GiB")
                    mem_used = mem_str.split("/")[0].strip()
                    if "GiB" in mem_used:
                        mem_val = float(mem_used.replace("GiB", "").strip()) * 1024
                    elif "MiB" in mem_used:
                        mem_val = float(mem_used.replace("MiB", "").strip())
                    elif "KiB" in mem_used:
                        mem_val = float(mem_used.replace("KiB", "").strip()) / 1024
                    else:
                        mem_val = float(mem_used.replace("B", "").strip()) / (1024 * 1024)
                    
                    resource_stats[svc]["cpu"].append(cpu_val)
                    resource_stats[svc]["mem"].append(mem_val)
                except Exception:
                    pass
        time.sleep(1)

def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8')
    except urllib.error.URLError as e:
        raise RuntimeError(f"HTTP request failed: {e}")

def http_post_json(url, body):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        raise RuntimeError(f"HTTP request failed: {e}")

def main():
    global profiling_active
    print(f"\n{Colors.HEADER}========================================================================{Colors.ENDC}")
    print(f"{Colors.HEADER}                  VINU INTEGRATION TESTING SUITE                       {Colors.ENDC}")
    print(f"{Colors.HEADER}========================================================================{Colors.ENDC}\n")

    # Step 0: Ensure Docker is running and compose down previous services
    log_info("Ensuring previous integration containers are stopped...")
    run_cmd(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"], check=False)

    # Clean up previous local folders
    if DATA_DIR.exists():
        log_info("Wiping stale integration data folder...")
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "shared").mkdir(exist_ok=True)

    # Write watchlist.json to shared volume BEFORE containers start
    watchlist_path = DATA_DIR / "shared" / "watchlist.json"
    watchlist_path.write_text(json.dumps({"tickers": ["AAPL"]}))
    log_info("Watchlist seeded with {'tickers': ['AAPL']}")

    # Copy env files if they are missing
    modules = ["vinu-components/vinu-news", "vinu-components/vinu-stock-price", "vinu-components/vinu-features", "vinu-components/vinu-correlation", "vinu-components/vinu-strategy", "vinu-components/vinu-simulator"]
    for mod in modules:
        env_file = Path(mod) / ".env"
        env_example = Path(mod) / ".env.example"
        if env_example.exists() and not env_file.exists():
            log_info(f"Copying {env_example} to {env_file}...")
            shutil.copy(env_example, env_file)

    step_times = {}
    container_ids = {}

    try:
        # Step 1: Spin up stack
        t_start = time.time()
        log_info("Building and launching Docker Compose stack...")
        run_cmd(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--build"])
        step_times["Build & Startup"] = time.time() - t_start

        # Step 2: Resolve container IDs
        log_info("Resolving container IDs for profiling...")
        container_ids = {}
        for svc in SERVICES:
            res = subprocess.run(
                ["docker", "compose", "-f", COMPOSE_FILE, "ps", "-q", svc],
                capture_output=True, text=True
            )
            cid = res.stdout.strip()
            container_ids[svc] = cid
            if not cid:
                log_warning(f"Could not resolve Container ID for service '{svc}'")
            else:
                log_info(f"Resolved service '{svc}' -> container {cid[:12]}")

        # Start resource profiling thread
        profiling_thread = threading.Thread(target=profiling_loop, args=(container_ids,), daemon=True)
        profiling_thread.start()

        # Step 3: Wait for HTTP APIs to be ready
        t_start = time.time()
        log_info("Waiting for HTTP APIs to be healthy/responsive...")
        apis = {
            "news-api": "http://localhost:8080/settings",
            "stock-api": "http://localhost:8081/settings",
            "features-api": "http://localhost:8082/presets",
            "correlation-api": "http://localhost:8083/settings",
            "strategy-api": "http://localhost:8084/strategies",
            "simulator-api": "http://localhost:8085/health"
        }
        
        for api_name, url in apis.items():
            ready = False
            for attempt in range(30):
                try:
                    http_get(url)
                    ready = True
                    log_info(f"  {api_name} is READY!")
                    break
                except Exception:
                    time.sleep(1)
            if not ready:
                log_fail(f"API {api_name} failed to become healthy within 30 seconds!")
                sys.exit(1)
        step_times["API Readiness"] = time.time() - t_start

        # Step 4: Seed Stock Prices inside stock-api container
        t_start = time.time()
        log_info("Seeding AAPL stock price data (Parquet + SQLite) inside stock-api...")
        stock_seed_code = """
import sqlite3
import pyarrow as pa
import pyarrow.parquet as pq
import time
import os

# Seed meta.db
conn = sqlite3.connect('/data/meta.db')
conn.execute('PRAGMA journal_mode = WAL')
conn.execute('PRAGMA busy_timeout = 30000')
conn.execute('CREATE TABLE IF NOT EXISTS symbol_catalog (symbol TEXT PRIMARY KEY, provider TEXT, first_bar_ts INTEGER, last_bar_ts INTEGER, archive_through TEXT, live_file TEXT, backfill_status TEXT, updated_at INTEGER, has_adj_data INTEGER, gap_count INTEGER, last_validation_at INTEGER)')
conn.execute('CREATE TABLE IF NOT EXISTS watchlist_tickers (ticker TEXT PRIMARY KEY, added_at INTEGER)')
conn.execute('CREATE TABLE IF NOT EXISTS vinu_settings (key TEXT PRIMARY KEY, value TEXT)')

now_ts = int(time.time())
base_ts = now_ts - 60 * 86400 # 60 days ago

conn.execute('INSERT OR REPLACE INTO symbol_catalog (symbol, provider, first_bar_ts, last_bar_ts, backfill_status, updated_at) VALUES ("AAPL", "test", ?, ?, "complete", ?)', (base_ts, now_ts, now_ts))
conn.execute('INSERT OR REPLACE INTO watchlist_tickers (ticker, added_at) VALUES ("AAPL", ?)', (now_ts,))
conn.execute('INSERT OR REPLACE INTO vinu_settings (key, value) VALUES ("poll_interval_sec", "60")')
conn.execute('INSERT OR REPLACE INTO vinu_settings (key, value) VALUES ("default_provider", "test")')
conn.execute('INSERT OR REPLACE INTO vinu_settings (key, value) VALUES ("data_root", "/data")')
conn.commit()
conn.close()

# Generate daily-spaced candles to compute SMA, MOM, ADX indicators
bars = []
for i in range(62):
    bar_ts = base_ts + i * 86400
    # Create an upward trend with some volatility
    close_price = 100.0 + i * 0.5 + (1.5 if i % 3 == 0 else -0.5)
    bars.append({
        'symbol': 'AAPL',
        'provider': 'test',
        'bar_ts': int(bar_ts),
        'open': float(close_price - 0.5),
        'high': float(close_price + 1.2),
        'low': float(close_price - 1.2),
        'close': float(close_price),
        'volume': 1500000.0,
        'vwap': float(close_price),
        'trades': int(120),
        'adj_factor': 1.0
    })

fields = [
    ('symbol', pa.string()),
    ('provider', pa.string()),
    ('bar_ts', pa.int64()),
    ('open', pa.float64()),
    ('high', pa.float64()),
    ('low', pa.float64()),
    ('close', pa.float64()),
    ('volume', pa.float64()),
    ('vwap', pa.float64()),
    ('trades', pa.int64()),
    ('adj_factor', pa.float64()),
]
schema = pa.schema(fields)
table = pa.Table.from_pylist(bars, schema=schema)
os.makedirs('/data/prices/1m/AAPL/archive', exist_ok=True)
pq.write_table(table, '/data/prices/1m/AAPL/archive/2026.parquet')
print('AAPL stock seeded successfully!')
"""
        run_cmd(["docker", "compose", "-f", COMPOSE_FILE, "exec", "-T", "stock-api", "python", "-c", stock_seed_code])
        step_times["Seed Stock Prices"] = time.time() - t_start

        # Step 5: Seed News articles inside news-api container
        t_start = time.time()
        log_info("Seeding AAPL news sentiment articles (SQLite) inside news-api...")
        news_seed_code = """
import sqlite3
import time
import os

conn = sqlite3.connect('/data/news.db')
conn.execute('PRAGMA journal_mode = WAL')
conn.execute('PRAGMA busy_timeout = 30000')
conn.execute('CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, headline TEXT, summary TEXT, source TEXT, link TEXT, sort_ts INTEGER, region TEXT, tier INTEGER, category TEXT, priority TEXT, sentiment TEXT, sentiment_score INTEGER, impact TEXT, tickers TEXT, lang TEXT, threat_level TEXT, threat_cat TEXT, threat_conf REAL, source_flag INTEGER, entities_json TEXT, cluster_id TEXT, is_lead INTEGER, thread_id TEXT)')
conn.execute('CREATE TABLE IF NOT EXISTS article_ticker_mentions (id TEXT PRIMARY KEY, article_id TEXT REFERENCES articles(id), ticker TEXT, dominance REAL, is_primary INTEGER, UNIQUE(article_id, ticker))')
conn.execute('CREATE TABLE IF NOT EXISTS watchlist_tickers (ticker TEXT PRIMARY KEY, added_at INTEGER)')
conn.execute('CREATE TABLE IF NOT EXISTS vinu_settings (key TEXT PRIMARY KEY, value TEXT)')

now_ts = int(time.time())
base_ts = now_ts - 60 * 86400

conn.execute('INSERT OR REPLACE INTO watchlist_tickers (ticker, added_at) VALUES ("AAPL", ?)', (now_ts,))
conn.execute('INSERT OR REPLACE INTO vinu_settings (key, value) VALUES ("mode", "ticker")')
conn.execute('INSERT OR REPLACE INTO vinu_settings (key, value) VALUES ("poll_interval_sec", "600")')
conn.execute('INSERT OR REPLACE INTO vinu_settings (key, value) VALUES ("llm_analysis_mode", "manual")')

# Generate 20 articles mapped perfectly to daily stock candle timestamps
for i in range(20):
    art_ts = base_ts + i * 2 * 86400  # Spread out
    sentiment = "bullish" if i % 4 != 0 else "bearish"
    sentiment_score = 80 if sentiment == "bullish" else -80
    impact = "high_bullish" if sentiment == "bullish" else "high_bearish"
    
    art_id = f"art_{i}"
    conn.execute(
        'INSERT OR REPLACE INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (art_id, f"AAPL update {i}", f"AAPL summary {i}", "Source", f"http://aapl-{i}.com", int(art_ts), "US", 1, "MARKETS", "high", sentiment, sentiment_score, impact, "AAPL", "en", "none", "none", 0.0, 0, "{}", f"cluster_{i}", 1, f"thread_{i}")
    )
    conn.execute('INSERT OR REPLACE INTO article_ticker_mentions VALUES (?, ?, ?, ?, ?)', (f"mention_{i}", art_id, "AAPL", 1.0, 1))

conn.commit()
conn.close()
print('AAPL news seeded successfully!')
"""
        run_cmd(["docker", "compose", "-f", COMPOSE_FILE, "exec", "-T", "news-api", "python", "-c", news_seed_code])
        step_times["Seed News Articles"] = time.time() - t_start

        # Sync watchlists
        log_info("Syncing watchlists on APIs...")
        http_post_json("http://localhost:8081/watchlist/sync", {})
        http_post_json("http://localhost:8080/watchlist/sync", {})

        # Step 6: Trigger Correlation Compute
        t_start = time.time()
        log_info("Triggering correlation computation via CLI inside correlation-api...")
        run_cmd(["docker", "compose", "-f", COMPOSE_FILE, "exec", "-T", "correlation-api", "vinu-correlation-compute", "AAPL"])
        step_times["Correlation Compute"] = time.time() - t_start

        # Step 7: Trigger Strategy Evaluation
        t_start = time.time()
        log_info("Evaluating strategies via strategy-api (ma_crossover and news_aware_momentum)...")
        res_ma = http_post_json("http://localhost:8084/strategies/ma_crossover/evaluate?symbols=AAPL", {})
        log_info(f"  ma_crossover evaluation result run_id: {res_ma.get('run_id')}")
        
        res_news = http_post_json("http://localhost:8084/strategies/news_aware_momentum/evaluate?symbols=AAPL", {})
        log_info(f"  news_aware_momentum evaluation result run_id: {res_news.get('run_id')}")
        step_times["Strategy Evaluation"] = time.time() - t_start

        # Step 8: Trigger Simulator Backtest
        t_start = time.time()
        log_info("Running simulator backtest via simulator-api...")
        
        # Calculate simulation dates covering mock data range
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        start_date_str = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
        
        sim_ma_body = {
            "strategy_name": "ma_crossover",
            "start_date": start_date_str,
            "end_date": tomorrow_str,
            "initial_capital": 100000.0,
            "transaction_cost_pct": 0.001,
            "slippage_pct": 0.0005,
            "benchmark_tickers": ["AAPL"],
            "allow_short": True
        }
        res_sim_ma = http_post_json("http://localhost:8085/simulate", sim_ma_body)
        log_success(f"ma_crossover backtest completed! Trade count: {res_sim_ma.get('trade_count')}, Equity points: {res_sim_ma.get('equity_points')}")
        
        sim_news_body = {
            "strategy_name": "news_aware_momentum",
            "start_date": start_date_str,
            "end_date": tomorrow_str,
            "initial_capital": 100000.0,
            "transaction_cost_pct": 0.001,
            "slippage_pct": 0.0005,
            "benchmark_tickers": ["AAPL"],
            "allow_short": True
        }
        res_sim_news = http_post_json("http://localhost:8085/simulate", sim_news_body)
        log_success(f"news_aware_momentum backtest completed! Trade count: {res_sim_news.get('trade_count')}, Equity points: {res_sim_news.get('equity_points')}")
        step_times["Simulator Backtest"] = time.time() - t_start

        log_success("All pipeline integration steps completed successfully!")

    except Exception as e:
        log_fail(f"Integration tests encountered an error: {e}")
    finally:
        # Stop resource profiling
        profiling_active = False
        
        # Collect final OOM check and logs before tearing down
        log_info("Checking containers for OOM flags...")
        for svc, cid in container_ids.items():
            if not cid:
                continue
            res = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.OOMKilled}}", cid],
                capture_output=True, text=True
            )
            if res.stdout.strip() == "true":
                resource_stats[svc]["oom"] = True
                log_fail(f"Container '{svc}' was KILLED by Out-Of-Memory (OOM)!")
            else:
                log_info(f"Container '{svc}' did not encounter OOM.")

        # Diagnose Container Logs for tracebacks/errors
        log_info("Scanning container logs for errors/exceptions...")
        log_diagnostics = {}
        for svc in SERVICES:
            res = subprocess.run(
                ["docker", "compose", "-f", COMPOSE_FILE, "logs", "--no-color", svc],
                capture_output=True, text=True
            )
            logs = res.stdout
            logs_lines = logs.splitlines()
            errors = []
            idx = 0
            while idx < len(logs_lines):
                line = logs_lines[idx]
                line_lower = line.lower()
                if "traceback" in line_lower or "exception" in line_lower or " error: " in line_lower or " critical: " in line_lower:
                    # Grab a chunk of 15 lines of context
                    chunk = logs_lines[idx:idx+15]
                    errors.append("\n  ".join(chunk))
                    idx += 14
                idx += 1
            if errors:
                log_diagnostics[svc] = errors[:3] # cap at 3 logs for summary
                log_warning(f"Service '{svc}' logged exceptions/errors!")

        # Step 9: Shut down Docker compose
        log_info("Tearing down integration containers...")
        run_cmd(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"], check=False)

        # Print final metrics report
        print(f"\n{Colors.HEADER}========================================================================{Colors.ENDC}")
        print(f"{Colors.HEADER}                    INTEGRATION PERFORMANCE REPORT                      {Colors.ENDC}")
        print(f"{Colors.HEADER}========================================================================{Colors.ENDC}\n")

        print(f"{Colors.BOLD}{'Pipeline Step':<30} {'Execution Time':<15}{Colors.ENDC}")
        print("-" * 50)
        for step, duration in step_times.items():
            print(f"{step:<30} {duration:.2f}s")
        print()

        print(f"{Colors.BOLD}{'Service Name':<25} {'Peak CPU %':<15} {'Peak RAM (MiB)':<18} {'OOM Killed':<12}{Colors.ENDC}")
        print("-" * 75)
        for svc in SERVICES:
            cpus = resource_stats[svc]["cpu"]
            mems = resource_stats[svc]["mem"]
            peak_cpu = max(cpus) if cpus else 0.0
            peak_mem = max(mems) if mems else 0.0
            oom_str = f"{Colors.FAIL}YES{Colors.ENDC}" if resource_stats[svc]["oom"] else "No"
            print(f"{svc:<25} {peak_cpu:>8.1f}%     {peak_mem:>12.1f} MiB       {oom_str:<12}")
        print()

        if log_diagnostics:
            print(f"\n{Colors.WARNING}========================================================================{Colors.ENDC}")
            print(f"{Colors.WARNING}                        LOG DIAGNOSTICS DETECTED                        {Colors.ENDC}")
            print(f"{Colors.WARNING}========================================================================{Colors.ENDC}")
            for svc, logs in log_diagnostics.items():
                print(f"\n{Colors.BOLD}Service: {svc}{Colors.ENDC}")
                for log in logs:
                    print(f"  {log}")
            print()
        else:
            log_success("No exceptions or critical errors detected in the container logs!")

if __name__ == "__main__":
    main()
