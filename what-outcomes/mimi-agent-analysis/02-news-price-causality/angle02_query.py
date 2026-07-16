import requests, json, time, sys
from datetime import datetime, timezone

BASE_NEWS = 'http://localhost:8080'
BASE_PRICE = 'http://localhost:8081'
BASE_CORR = 'http://localhost:8083'
BASE_STRAT = 'http://localhost:8084'

TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
TIMEFRAMES = ['1d', '4h', '1h', '15m']

# 2022-01-03 00:00 UTC (first trading day) to now
FIRST_TRADING_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": detail}))

def check(label, elapsed, r, trunc=500):
    ok = 200 <= r.status_code < 300
    detail = ''
    if ok:
        try: data = r.json()
        except: data = r.text[:trunc]
        if isinstance(data, dict): detail = json.dumps(data, indent=2)[:trunc]
        elif isinstance(data, list): detail = f"{len(data)} items"
        else: detail = str(data)[:trunc]
    else:
        detail = f"HTTP {r.status_code}: {r.text[:300]}"
    log(label, elapsed, 'PASS' if ok else 'FAIL', detail)
    return ok, r

# ── Section 1: Health Checks ──
print("=== SECTION 1: SERVICE HEALTH ===")
for label, url in [
    ('health_news', f'{BASE_NEWS}/health'),
    ('health_price', f'{BASE_PRICE}/health'),
    ('health_corr', f'{BASE_CORR}/health'),
    ('health_strat', f'{BASE_STRAT}/health'),
]:
    t0 = time.time()
    try: r = requests.get(url, timeout=10)
    except Exception as e: log(label, time.time()-t0, 'FAIL', str(e)); continue
    check(label, time.time()-t0, r)

# ── Section 2: Correlation Service – Core Stats ──
print("\n=== SECTION 2: CORRELATION STATS (all 4 tickers) ===")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_CORR}/correlation/{sym}', timeout=30)
    except Exception as e: log(f'correlation_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    ok, _ = check(f'correlation_{sym}', time.time()-t0, r)
    if ok:
        d = r.json()
        log(f'correlation_{sym}_summary', 0, 'INFO',
            f'news_return_corr={d.get("news_return_corr")}, '
            f'sentiment_return_corr={d.get("sentiment_return_corr")}, '
            f'granger_p={d.get("granger_p_value")}, '
            f'best_lag={d.get("best_lag_minutes")}min, '
            f'sample_n={d.get("sample_size")}')

# ── Section 3: Impact Events (with price reaction) ──
print("\n=== SECTION 3: IMPACT EVENTS ===")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_CORR}/impact/{sym}', timeout=30)
    except Exception as e: log(f'impact_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    ok, _ = check(f'impact_{sym}', time.time()-t0, r, trunc=800)
    if ok:
        d = r.json()
        if isinstance(d, dict):
            ec = d.get('event_count', 0) if isinstance(d.get('data'), dict) else (d if isinstance(d.get('events'), list) else 0)
            log(f'impact_{sym}_summary', 0, 'INFO',
                f'{ec} events, '
                f'high_impact_bullish={d.get("high_impact_bullish_events", "?")}, '
                f'high_impact_bearish={d.get("high_impact_bearish_events", "?")}, '
                f'avg_price_drop_30m={d.get("avg_price_drop_30m", "?")}')

# Also get batch correlation
print("\n--- 3a: BATCH CORRELATION ---")
t0 = time.time()
try: r = requests.get(f'{BASE_CORR}/correlation/batch', params={'symbols': ','.join(TICKERS)}, timeout=60)
except Exception as e: log('correlation_batch', time.time()-t0, 'FAIL', str(e)); pass
else: check('correlation_batch', time.time()-t0, r)

# ── Section 4: News Volume Baseline (per-session) ──
print("\n=== SECTION 4: NEWS VOLUME BASELINE ===")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_CORR}/baseline/{sym}', timeout=30)
    except Exception as e: log(f'baseline_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    ok, _ = check(f'baseline_{sym}', time.time()-t0, r, trunc=600)
    if ok:
        d = r.json()
        sessions = d.get('sessions', {}) if isinstance(d, dict) else {}
        session_str = '; '.join([f"{sess}: mean={info.get('mean','?')}" for sess, info in sessions.items()])
        log(f'baseline_{sym}_summary', 0, 'INFO',
            f'mean_daily={d.get("mean_daily_articles")}, sessions: {session_str}')

# ── Section 5: Drawdown Attribution ──
print("\n=== SECTION 5: DRAWDOWN ATTRIBUTION ===")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_CORR}/drawdown/{sym}', timeout=30)
    except Exception as e: log(f'drawdown_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    ok, _ = check(f'drawdown_{sym}', time.time()-t0, r, trunc=600)
    if ok:
        d = r.json()
        dd_count = d.get('drawdown_count', 0) if isinstance(d, dict) else 0
        log(f'drawdown_{sym}_summary', 0, 'INFO',
            f'{dd_count} drawdowns, '
            f'news_driven_pct={d.get("drawdowns", [{}])[0].get("attribution", {}).get("news_driven_pct", "?") if isinstance(d, dict) and d.get("drawdowns") else "?"}')

# ── Section 6: Event Study ──
print("\n=== SECTION 6: EVENT STUDY ===")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_CORR}/events/{sym}', timeout=30)
    except Exception as e: log(f'events_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    ok, _ = check(f'events_{sym}', time.time()-t0, r, trunc=400)
    if ok:
        data = r.json()
        count = data.get('count', 0) if isinstance(data, dict) else len(data) if isinstance(data, list) else '?'
        log(f'events_{sym}_summary', 0, 'INFO', f'{count} events')

# ── Section 7: Gap Analysis (session transitions) ──
print("\n=== SECTION 7: SESSION TRANSITION GAP ===")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_CORR}/gap/{sym}', timeout=30)
    except Exception as e: log(f'gap_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    check(f'gap_{sym}', time.time()-t0, r)

# ── Section 8: Story track (known bug) ──
print("\n=== SECTION 8: STORY TRACK ===")
for sym in TICKERS:
    t0 = time.time()
    try: r = requests.get(f'{BASE_CORR}/story/{sym}', timeout=15)
    except Exception as e: log(f'story_{sym}', time.time()-t0, 'FAIL', str(e)); continue
    check(f'story_{sym}', time.time()-t0, r)

# ── Section 9: Strategy Evaluation ──
print("\n=== SECTION 9: STRATEGY EVALUATION ===")
t0 = time.time()
try:
    r = requests.post(f'{BASE_STRAT}/strategies/adx_filtered_crossover/evaluate',
                       params={'symbols': ','.join(TICKERS)}, timeout=60)
except Exception as e: log('strategy_evaluate', time.time()-t0, 'FAIL', str(e)); pass
else: check('strategy_evaluate', time.time()-t0, r, trunc=1000)

# List strategies
t0 = time.time()
try: r = requests.get(f'{BASE_STRAT}/strategies', timeout=10)
except Exception as e: log('strategy_list', time.time()-t0, 'FAIL', str(e)); pass
else: check('strategy_list', time.time()-t0, r)

# Get the specific strategy definition
t0 = time.time()
try: r = requests.get(f'{BASE_STRAT}/strategies/adx_filtered_crossover', timeout=10)
except Exception as e: log('strategy_detail', time.time()-t0, 'FAIL', str(e)); pass
else: check('strategy_detail', time.time()-t0, r, trunc=600)

# ── Section 10: Price Data for Verifying Causality Input ──
print("\n=== SECTION 10: PRICE DATA (for causality verification) ===")
for sym in TICKERS:
    # Daily with indicators
    t0 = time.time()
    try:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
            'interval': '1d', 'from': FIRST_TRADING_TS, 'to': NOW_TS,
            'limit': 500, 'indicators': 'sma_10,sma_20,rsi_14'
        }, timeout=30)
    except Exception as e: log(f'candles_{sym}_1d_indicators', time.time()-t0, 'FAIL', str(e)); continue
    ok, _ = check(f'candles_{sym}_1d_indicators', time.time()-t0, r, trunc=300)
    if ok:
        data = r.json()
        count = data.get('count', 0)
        log(f'candles_{sym}_1d_indicators_count', 0, 'PASS' if count > 0 else 'WARN', f'{count} bars with indicators')

# ── Section 11: Summary ──
print("\n=== SECTION 11: SUMMARY ===")
log('total_execution_time', 0, 'DONE',
    'Angle 02: News-Price Causality complete')
