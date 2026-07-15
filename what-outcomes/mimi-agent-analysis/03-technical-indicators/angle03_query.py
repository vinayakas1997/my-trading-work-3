import requests, json, time, os, sys
from datetime import datetime, timezone

BASE_FEATURES = 'http://localhost:8082'
BASE_PRICE = 'http://localhost:8081'

TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
TIMEFRAMES = {'1d': '1d', '4h': '1h', '1h': '1h', '15m': '15m'}
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

INDICATOR_TESTS = {
    # (test_name, features_list, description)
    'trend_sma': (['sma_9', 'sma_21', 'sma_50', 'sma_200'], 'Simple Moving Averages (9,21,50,200)'),
    'trend_ema': (['ema_12', 'ema_26'], 'Exponential Moving Averages (12,26)'),
    'trend_macd': (['macd'], 'MACD'),
    'trend_macd_signal': (['macd_signal'], 'MACD Signal Line'),
    'trend_adx': (['adx_14'], 'Average Directional Index (14)'),
    'trend_supertrend': (['supertrend'], 'Supertrend'),
    'trend_aroon': (['aroon_up', 'aroon_down'], 'Aroon Up/Down'),
    'momentum_rsi': (['rsi_14', 'rsi_7'], 'RSI (14, 7)'),
    'momentum_cci': (['cci_20'], 'Commodity Channel Index (20)'),
    'momentum_williams_r': (['williams_r'], 'Williams %R'),
    'momentum_momentum': (['momentum'], 'Momentum N'),
    'momentum_roc': (['roc'], 'Rate of Change'),
    'volatility_atr': (['atr_14'], 'Average True Range (14)'),
    'volatility_bollinger': (['bb_upper_20', 'bb_mid_20', 'bb_lower_20'], 'Bollinger Bands (20,2)'),
    'volatility_vol': (['volatility_20d'], 'Volatility 20d'),
    'volume_obv': (['obv'], 'On-Balance Volume'),
    'volume_vwap': (['vwap'], 'VWAP'),
    'volume_ratio': (['volume_ratio_20'], 'Volume Ratio (20)'),
    'volume_cmf': (['cmf_20'], 'Chaikin Money Flow (20)'),
    'price_daily_return': (['daily_return'], 'Daily Return'),
    'price_high_low_spread': (['high_low_spread'], 'High-Low Spread'),
    'price_open_close_return': (['open_close_return'], 'Open-Close Return'),
    'price_stochastic': (['stoch_k', 'stoch_d'], 'Stochastic %K/%D'),
    'session': (['session'], 'Trading Session'),
}

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

def run_features_request(title, symbols, interval, features, tfrom, tto):
    t0 = time.time()
    try:
        r = requests.post(f'{BASE_FEATURES}/requests', json={
            'title': title, 'symbols': symbols, 'interval': interval,
            'features': features, 'from': tfrom, 'to': tto
        }, timeout=15)
    except Exception as e:
        log(f'{title}_create', time.time()-t0, 'FAIL', str(e))
        return None
    if r.status_code != 200:
        log(f'{title}_create', time.time()-t0, 'FAIL', f'HTTP {r.status_code}: {r.text[:300]}')
        return None
    req = r.json()
    rid = req.get('id')
    log(f'{title}_create', time.time()-t0, 'PASS', f'request_id={rid}, initial_status={req.get("status")}')

    t0 = time.time()
    try:
        r2 = requests.post(f'{BASE_FEATURES}/requests/{rid}/run', timeout=120)
    except Exception as e:
        log(f'{title}_run', time.time()-t0, 'FAIL', str(e))
        return None
    if r2.status_code != 200:
        log(f'{title}_run', time.time()-t0, 'FAIL', f'HTTP {r2.status_code}: {r2.text[:300]}')
        return None
    result = r2.json()
    status = result.get('status')
    rows = result.get('row_count', 0)
    fp = result.get('file_path', '')
    timed = round(time.time()-t0, 3)
    log(f'{title}_run', timed, 'PASS' if status == 'done' else 'WARN',
        f'status={status}, rows={rows}, path={os.path.basename(fp) if fp else "N/A"}')
    return result

# ── Section 1: Health Check ──
print("=== SECTION 1: FEATURES SERVICE HEALTH ===")
t0 = time.time()
try: r = requests.get(f'{BASE_FEATURES}/health', timeout=10)
except Exception as e: log('features_health', time.time()-t0, 'FAIL', str(e)); pass
else: check('features_health', time.time()-t0, r)

# ── Section 2: Test All 24 Indicators on AAPL 1d ──
print("\n=== SECTION 2: ALL 24 INDICATORS (AAPL 1d) ===")
for test_name, (features, desc) in INDICATOR_TESTS.items():
    log(f'indicator_{test_name}', 0, 'TESTING', f'{desc}: {features}')
    result = run_features_request(f'angle03_{test_name}', ['AAPL'], '1d', features, FIRST_TS, NOW_TS)

# ── Section 3: All Indicators on All 4 Tickers ──
print("\n=== SECTION 3: CORE INDICATORS ACROSS ALL TICKERS ===")
core_features = ['sma_9', 'sma_21', 'sma_50', 'rsi_14', 'adx_14', 'macd', 'bb_upper_20', 'bb_mid_20', 'bb_lower_20',
                 'atr_14', 'obv', 'daily_return', 'volatility_20d']
for sym in TICKERS:
    log(f'core_{sym}', 0, 'TESTING', f'Computing core indicators for {sym} 1d')
    result = run_features_request(f'angle03_core_{sym}', [sym], '1d', core_features, FIRST_TS, NOW_TS)
    if result:
        log(f'core_{sym}_result', 0, 'INFO',
            f'rows={result.get("row_count")}, status={result.get("status")}, '
            f'file={os.path.basename(result.get("file_path",""))}')

# ── Section 4: Parametric Testing ──
print("\n=== SECTION 4: PARAMETRIC TESTING (multiple periods) ===")
param_tests = [
    ('sma_periods', ['sma_9', 'sma_21', 'sma_50', 'sma_100', 'sma_200']),
    ('rsi_periods', ['rsi_7', 'rsi_14', 'rsi_21']),
    ('atr_periods', ['atr_7', 'atr_14', 'atr_21']),
    ('bollinger_periods', ['bb_upper_10', 'bb_mid_10', 'bb_lower_10', 'bb_upper_20', 'bb_mid_20', 'bb_lower_20']),
    ('ema_periods', ['ema_9', 'ema_12', 'ema_21', 'ema_26', 'ema_50']),
]
for test_name, features in param_tests:
    log(f'parametric_{test_name}', 0, 'TESTING', f'Testing {features}')
    run_features_request(f'angle03_{test_name}', ['AAPL'], '1d', features, FIRST_TS, NOW_TS)

# ── Section 5: Multi-timeframe ──
print("\n=== SECTION 5: CORE INDICATORS ACROSS TIMEFRAMES (AAPL) ===")
for tf_name, interval in TIMEFRAMES.items():
    log(f'timeframe_{tf_name}', 0, 'TESTING', f'Core indicators on AAPL {tf_name}')
    run_features_request(f'angle03_tf_{tf_name}', ['AAPL'], interval, core_features, FIRST_TS, NOW_TS)

# ── Section 6: Price Endpoint Built-in Indicators ──
print("\n=== SECTION 6: PRICE ENDPOINT BUILT-IN INDICATORS ===")
price_features = ['sma_20', 'rsi_14', 'daily_return', 'volatility_20d']
for sym in TICKERS:
    t0 = time.time()
    try:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
            'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS,
            'limit': 500, 'indicators': ','.join(price_features)
        }, timeout=30)
    except Exception as e:
        log(f'price_indicators_{sym}', time.time()-t0, 'FAIL', str(e))
        continue
    ok, _ = check(f'price_indicators_{sym}', time.time()-t0, r, trunc=300)
    if ok:
        data = r.json()
        count = data.get('count', 0)
        sample = data.get('data', [{}])[0] if data.get('data') else {}
        non_null = {k: v for k, v in sample.items() if k in price_features and v is not None}
        log(f'price_indicators_{sym}_summary', 0, 'PASS' if count > 0 else 'WARN',
            f'{count} bars, non-null indicators in first bar: {list(non_null.keys())}')

# ── Section 7: Summary ──
print("\n=== SECTION 7: PRESETS ===")
t0 = time.time()
try: r = requests.get(f'{BASE_FEATURES}/presets', timeout=10)
except Exception as e: log('presets', time.time()-t0, 'FAIL', str(e)); pass
else:
    ok, _ = check('presets', time.time()-t0, r)
    if ok:
        presets = r.json().get('data', [])
        for p in presets:
            log(f'preset_{p["name"]}', 0, 'INFO', f'{p["name"]}: {len(p["features"])} features')

log('total', 0, 'DONE', 'Angle 03: Technical Indicator Landscape complete')
