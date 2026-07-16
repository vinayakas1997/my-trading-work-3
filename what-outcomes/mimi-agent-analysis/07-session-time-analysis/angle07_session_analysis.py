"""Angle 07: Session/Time-of-Day Analysis — classifies trading into 5 sessions."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
BASE_CORR = 'http://localhost:8083'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000  # 2022-01-01
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

def classify_session(hour_et):
    if hour_et < 4:
        return 'closed'
    elif hour_et < 9:
        return 'london'
    elif hour_et < 9 or (hour_et == 9 and 0 < 30):
        return 'ny_premarket'
    elif hour_et < 16:
        return 'ny_regular'
    elif hour_et < 20:
        return 'ny_afterhours'
    else:
        return 'closed'

results = {}

# ── Step 1: Fetch 1h OHLCV ──
print("=== STEP 1: FETCH 1h OHLCV ===")
t0 = time.time()
ohlcv_1h = {}
for sym in TICKERS:
    t1 = time.time()
    try:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
            'interval': '1h', 'from': FIRST_TS, 'to': NOW_TS
        }, timeout=30)
        if r.status_code == 200:
            data = r.json().get('data', [])
            df = pd.DataFrame(data)
            if not df.empty and 'bar_ts' in df.columns:
                df['date'] = pd.to_datetime(df['bar_ts'], unit='s')
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
            ohlcv_1h[sym] = df
            log(f'fetch_{sym}', time.time()-t1, 'PASS', f'{len(df)} bars')
        else:
            log(f'fetch_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
    except Exception as e:
        log(f'fetch_{sym}', time.time()-t1, 'FAIL', str(e))
log('fetch_all', time.time()-t0, 'DONE', f'{len(ohlcv_1h)} tickers')

# Use synthetic fallback if no data
if not ohlcv_1h:
    log('fallback', 0, 'WARN', 'No OHLCV data — using synthetic 1h data')
    dates = pd.date_range('2022-01-01', periods=5000, freq='h')
    for sym in TICKERS:
        ohlcv_1h[sym] = pd.DataFrame({'close': np.random.randn(5000).cumsum() + 100},
                                      index=dates)

# ── Step 2: Session Classification ──
print("\n=== STEP 2: SESSION CLASSIFICATION ===")
try:
    import pytz
    ny_tz = pytz.timezone('America/New_York')
    has_pytz = True
except ImportError:
    has_pytz = False
    log('pytz', 0, 'WARN', 'pytz not available, using UTC hours')

t0 = time.time()
for sym in TICKERS:
    df = ohlcv_1h.get(sym)
    if df is None or df.empty:
        log(f'session_{sym}', 0, 'FAIL', 'No data')
        continue
    if has_pytz:
        df['hour_et'] = df.index.tz_localize('UTC').tz_convert(ny_tz).hour
    else:
        df['hour_et'] = df.index.hour  # approximate
    df['session'] = df['hour_et'].apply(classify_session)
    vc = df['session'].value_counts()
    transitions = (df['session'] != df['session'].shift(1)).sum()
    results[sym] = {'distribution': vc.to_dict(), 'transitions': int(transitions)}
    log(f'session_{sym}', time.time()-t0, 'PASS', f'dist={vc.to_dict()}, transitions={transitions}')
log('session_all', time.time()-t0, 'DONE')

# ── Step 3: Gap & Baseline API ──
print("\n=== STEP 3: CORRELATION API (BASELINE + GAP) ===")
t0 = time.time()
for sym in TICKERS:
    for ep_name, ep_path in [('baseline', f'{BASE_CORR}/baseline/{sym}'), ('gap', f'{BASE_CORR}/gap/{sym}')]:
        t1 = time.time()
        try:
            r = requests.get(ep_path, timeout=10)
            if r.status_code == 200:
                d = r.json()
                log(f'{ep_name}_{sym}', time.time()-t1, 'PASS', str(d)[:300])
            else:
                log(f'{ep_name}_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
        except Exception as e:
            log(f'{ep_name}_{sym}', time.time()-t1, 'FAIL', str(e))

# ── Step 4: Session Transition Gap Analysis ──
print("\n=== STEP 4: SESSION TRANSITION GAPS ===")
t0 = time.time()
for sym in TICKERS:
    df = ohlcv_1h.get(sym)
    if df is None or df.empty:
        continue
    if 'session' not in df.columns:
        continue
    transitions = df[df['session'] != df['session'].shift(1)]
    gap_count = len(transitions)
    premarket_count = len(transitions[transitions['session'] == 'ny_premarket'])
    afterhours_count = len(transitions[transitions['session'] == 'ny_afterhours'])
    log(f'gaps_{sym}', time.time()-t0, 'PASS',
        f'total_transitions={gap_count}, premarket={premarket_count}, afterhours={afterhours_count}')

# ── Step 5: Multi-timeframe Session Stats ──
print("\n=== STEP 5: MULTI-TIMEFRAME ===")
intervals = {'1d': '1d', '4h': '1h', '1h': '1h', '15m': '15m'}
for tf_name, interval in intervals.items():
    for sym in TICKERS:
        if tf_name == '1h':
            df = ohlcv_1h.get(sym)
        else:
            df = None
            try:
                r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
                    'interval': interval, 'from': FIRST_TS, 'to': NOW_TS
                }, timeout=15)
                if r.status_code == 200:
                    data = r.json().get('data', [])
                    df = pd.DataFrame(data)
                    if not df.empty and 'bar_ts' in df.columns:
                        df['date'] = pd.to_datetime(df['bar_ts'], unit='s')
                        df.set_index('date', inplace=True)
            except:
                pass
        if df is not None and not df.empty:
            if has_pytz:
                df['hour_et'] = df.index.tz_localize('UTC').tz_convert(ny_tz).hour
            df['session'] = df['hour_et'].apply(classify_session)
            vc = df['session'].value_counts()
            log(f'session_{tf_name}_{sym}', 0, 'PASS', f'dist={vc.to_dict()}')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 07 session analysis finished')
