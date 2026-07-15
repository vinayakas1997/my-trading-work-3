import requests, json, time, sys
from datetime import datetime, timezone, timedelta

BASE_NEWS = 'http://localhost:8080'
BASE_PRICE = 'http://localhost:8081'
BASE_CORR = 'http://localhost:8083'

TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
TIMEFRAMES = ['1d', '4h', '1h', '15m']
TIMEFRAME_INTERVAL = {'1d': '1d', '4h': '1h', '1h': '1h', '15m': '15m'}

FIRST_TRADING_TS = 1641168000  # 2022-01-03 00:00 UTC (first trading day)
START_TS = FIRST_TRADING_TS
END_TS = int(datetime.now(timezone.utc).timestamp())
END_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": detail}))

def check(label, elapsed, r, trunc=500):
    ok = 200 <= r.status_code < 300
    detail = ''
    if ok:
        try: data = r.json()
        except: data = r.text[:trunc]
        if isinstance(data, dict): detail = json.dumps(data, indent=2)[:trunc]
        elif isinstance(data, list): detail = f"{len(data)} items, first: {json.dumps(data[0] if data else {}, indent=2)[:300]}"
        else: detail = str(data)[:trunc]
    else:
        detail = f"HTTP {r.status_code}: {r.text[:300]}"
    log(label, elapsed, 'PASS' if ok else 'FAIL', detail)
    return ok, r

# ── Section 1: Health Check ──
print("=== SECTION 1: SERVICE HEALTH ===")
for label, url in [
    ('health_news', f'{BASE_NEWS}/health'),
    ('health_price', f'{BASE_PRICE}/health'),
    ('health_corr', f'{BASE_CORR}/health'),
]:
    t0 = time.time()
    try: r = requests.get(url, timeout=10)
    except Exception as e: log(label, time.time()-t0, 'FAIL', str(e)); continue
    check(label, time.time()-t0, r)

# ── Section 2: News Pipeline Tests ──
print("\n=== SECTION 2: NEWS PIPELINE (all 12 dimensions) ===")

# 2a: Ticker news for each ticker
print("\n--- 2a: TICKER NEWS ---")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_NEWS}/ticker/{sym}', params={'days': 365, 'limit': 5}, timeout=10)
    except Exception as e: log(f'ticker_news_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    ok, resp = check(f'ticker_news_{sym}', time.time()-t0, r)
    if ok:
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            art = data[0]
            keys_found = list(art.keys())
            log(f'ticker_news_{sym}_fields', 0, 'INFO', f'Article keys: {keys_found}')

# 2b: High-impact news
print("\n--- 2b: HIGH-IMPACT NEWS ---")
for hours in [48, 720]:  # 720 is API max
    t0 = time.time()
    try: r = requests.get(f'{BASE_NEWS}/high-impact', params={'hours': hours, 'limit': 10}, timeout=10)
    except Exception as e: log(f'high_impact_{hours}h', time.time()-t0, 'FAIL', str(e)); continue
    check(f'high_impact_{hours}h', time.time()-t0, r)

# 2c: Ticker stats
print("\n--- 2c: TICKER STATS ---")
for sym in TICKERS:
    for days in [7, 30, 365]:
        t0 = time.time()
        try: r = requests.get(f'{BASE_NEWS}/stats/ticker/{sym}', params={'days': days}, timeout=10)
        except Exception as e: log(f'stats_{sym}_{days}d', time.time()-t0, 'FAIL', str(e)); continue
        check(f'stats_{sym}_{days}d', time.time()-t0, r, trunc=800)

# 2d: Threads
print("\n--- 2d: THREAD TRACKING ---")
t0 = time.time()
try: r = requests.get(f'{BASE_NEWS}/threads/active', params={'hours': 48, 'limit': 10}, timeout=10)
except Exception as e: log('threads_active', time.time()-t0, 'FAIL', str(e)); pass
else: check('threads_active', time.time()-t0, r)

# 2e: Latest news
print("\n--- 2e: LATEST NEWS ---")
t0 = time.time()
try: r = requests.get(f'{BASE_NEWS}/latest', params={'limit': 5}, timeout=10)
except Exception as e: log('latest_news', time.time()-t0, 'FAIL', str(e)); pass
else: check('latest_news', time.time()-t0, r)

# 2f: Settings
print("\n--- 2f: SETTINGS ---")
t0 = time.time()
try: r = requests.get(f'{BASE_NEWS}/settings', timeout=10)
except Exception as e: log('settings', time.time()-t0, 'FAIL', str(e)); pass
else: check('settings', time.time()-t0, r)

# 2g: Search
print("\n--- 2g: SEARCH ---")
for q in ['earnings', 'AI', 'stock split']:
    t0 = time.time()
    try: r = requests.get(f'{BASE_NEWS}/search', params={'q': q, 'limit': 3}, timeout=10)
    except Exception as e: log(f'search_{q}', time.time()-t0, 'FAIL', str(e)); continue
    check(f'search_{q}', time.time()-t0, r)

# ── Section 3: Price Data Tests ──
print("\n=== SECTION 3: PRICE DATA (4 tickers x 4 timeframes) ===")

# Test known bug: days param vs from/to timestamps
print("\n--- 3a: DAYS PARAM BUG VERIFICATION ---")
t0 = time.time()
try: r_days = requests.get(f'{BASE_PRICE}/candles/AAPL', params={'interval': '1d', 'days': 5}, timeout=10)
except Exception as e: log('candles_days_param', time.time()-t0, 'FAIL', str(e)); pass
else:
    ok, _ = check('candles_days_param', time.time()-t0, r_days)
    if ok:
        data = r_days.json()
        count = data.get('count', 0) if isinstance(data, dict) else 0
        log('candles_days_param_count', 0, 'BUG' if count == 0 else 'OK',
            f'Returned {count} bars with days=5 (expected 5)')

# 3b: Price with timestamps (workaround)
print("\n--- 3b: PRICE WITH TIMESTAMPS (workaround) ---")
for sym in TICKERS:
    for tf_name in TIMEFRAMES:
        interval = TIMEFRAME_INTERVAL[tf_name]
        t0 = time.time()
        try:
            r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
                'interval': interval, 'from': START_TS, 'to': END_TS, 'limit': 100
            }, timeout=30)
        except Exception as e:
            log(f'candles_{sym}_{tf_name}', time.time()-t0, 'FAIL', str(e))
            continue
        ok, _ = check(f'candles_{sym}_{tf_name}', time.time()-t0, r)
        if ok:
            data = r.json()
            count = data.get('count', 0) if isinstance(data, dict) else 0
            log(f'candles_{sym}_{tf_name}_count', 0, 'PASS' if count > 0 else 'WARN',
                f'{count} bars returned')

# 3c: Catalog
print("\n--- 3c: CATALOG ---")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_PRICE}/catalog/{sym}', timeout=10)
    except Exception as e: log(f'catalog_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    check(f'catalog_{sym}', time.time()-t0, r)

# ── Section 4: Correlation Service Tests ──
print("\n=== SECTION 4: CORRELATION SERVICE ===")
for sym in TICKERS:
    for endpoint in ['correlation', 'impact', 'baseline', 'drawdown', 'events', 'story']:
        t0 = time.time()
        try: r = requests.get(f'{BASE_CORR}/{endpoint}/{sym}', timeout=15)
        except Exception as e: log(f'{endpoint}_{sym}', time.time()-t0, 'FAIL', str(e)); continue
        check(f'{endpoint}_{sym}', time.time()-t0, r, trunc=600)

# ── Section 5: Summary Stats ──
print("\n=== SECTION 5: SUMMARY ===")
t_all = time.time()
log('total_execution_time', time.time() - t_all, 'DONE',
    'Angle 01: News-First Analysis complete')
