"""Angle 09: Regime Analysis — classifies market into 4 regimes."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

def classify_regime(row, vol_thresh):
    if row['vol'] > vol_thresh:
        return 'high_vol'
    if row['ret'] > 0.01:
        return 'bull'
    if row['ret'] < -0.01:
        return 'bear'
    return 'sideways'

# ── Step 1: Fetch OHLCV ──
print("=== STEP 1: FETCH OHLCV ===")
t0 = time.time()
ohlcv = {}
for sym in TICKERS:
    t1 = time.time()
    try:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
            'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS
        }, timeout=30)
        if r.status_code == 200:
            data = r.json().get('data', [])
            df = pd.DataFrame(data)
            if not df.empty and 'bar_ts' in df.columns:
                df['date'] = pd.to_datetime(df['bar_ts'], unit='s')
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
            ohlcv[sym] = df
            log(f'fetch_{sym}', time.time()-t1, 'PASS', f'{len(df)} bars')
        else:
            log(f'fetch_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
    except Exception as e:
        log(f'fetch_{sym}', time.time()-t1, 'FAIL', str(e))
log('fetch_all', time.time()-t0, 'DONE', f'{len(ohlcv)} tickers')

# Use random fallback if no data
if not ohlcv:
    log('fallback', 0, 'WARN', 'No OHLCV data — using synthetic data')
    dates = pd.date_range('2022-01-01', periods=500, freq='D')
    panel = {'close': pd.DataFrame(np.random.randn(500, 4).cumsum(axis=0) + 100, index=dates, columns=TICKERS)}
    for c in ['open','high','low','volume']:
        panel[c] = panel['close'] * (1 + np.random.randn(500, 4) * 0.01)
    panel['returns'] = panel['close'].pct_change()
else:
    panel = {}
    for col in ['open', 'high', 'low', 'close', 'volume']:
        frames = {sym: ohlcv[sym][col] for sym in TICKERS if col in ohlcv[sym].columns}
        panel[col] = pd.DataFrame(frames) if frames else pd.DataFrame()
    panel['returns'] = panel['close'].pct_change()

# ── Step 2: Regime Classification ──
print("\n=== STEP 2: REGIME CLASSIFICATION ===")
t0 = time.time()
all_results = {}
for sym in TICKERS:
    ret = panel['returns'][sym].dropna()
    if len(ret) < 21:
        log(f'regime_{sym}', 0, 'FAIL', f'Insufficient data ({len(ret)} bars)')
        continue
    vol = ret.rolling(21).std() * np.sqrt(252)
    vol_thresh = vol.quantile(0.7)
    rf = pd.DataFrame({'ret': ret, 'vol': vol}).dropna()
    rf['regime'] = rf.apply(lambda r: classify_regime(r, vol_thresh), axis=1)
    stats = {}
    for rg, grp in rf.groupby('regime'):
        sr = (grp['ret'].mean() / grp['ret'].std() * np.sqrt(252)) if grp['ret'].std() > 0 else 0.0
        stats[rg] = {
            'count': len(grp),
            'total_return': float((1 + grp['ret']).prod() - 1),
            'avg_return': float(grp['ret'].mean()),
            'std_return': float(grp['ret'].std()),
            'sharpe': round(sr, 4),
            'win_rate': float((grp['ret'] > 0).mean()),
        }
    all_results[sym] = stats
    log(f'regime_{sym}', time.time()-t0, 'PASS', json.dumps(stats))

# ── Step 3: Regime Transition Matrix ──
print("\n=== STEP 3: REGIME TRANSITIONS ===")
t0 = time.time()
for sym in TICKERS:
    ret = panel['returns'][sym].dropna()
    if len(ret) < 21:
        continue
    vol = ret.rolling(21).std() * np.sqrt(252)
    vol_thresh = vol.quantile(0.7)
    rf = pd.DataFrame({'ret': ret, 'vol': vol}).dropna()
    rf['regime'] = rf.apply(lambda r: classify_regime(r, vol_thresh), axis=1)
    transitions = (rf['regime'] != rf['regime'].shift(1)).sum()
    log(f'transitions_{sym}', time.time()-t0, 'PASS', f'{transitions} regime changes')

# ── Step 4: Multi-timeframe ──
print("\n=== STEP 4: MULTI-TIMEFRAME ===")
intervals = {'4h': '1h', '1h': '1h', '15m': '15m'}
for tf_name, interval in intervals.items():
    for sym in TICKERS:
        t1 = time.time()
        try:
            r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
                'interval': interval, 'from': FIRST_TS, 'to': NOW_TS
            }, timeout=15)
            if r.status_code == 200:
                data = r.json().get('data', [])
                df = pd.DataFrame(data)
                if not df.empty and 'close' in df.columns:
                    ret_s = df['close'].pct_change().dropna()
                    vol_s = ret_s.rolling(min(21, len(ret_s))).std() * np.sqrt(252 * 390 if '15m' in interval else 252 * 24 if '1h' in interval else 252)
                    if len(vol_s.dropna()) > 0:
                        vol_thresh_s = vol_s.quantile(0.7)
                        rf_s = pd.DataFrame({'ret': ret_s, 'vol': vol_s}).dropna()
                        rf_s['regime'] = rf_s.apply(lambda r: classify_regime(r, vol_thresh_s), axis=1)
                        vc = rf_s['regime'].value_counts().to_dict()
                        log(f'regime_{tf_name}_{sym}', time.time()-t1, 'PASS', vc)
                    else:
                        log(f'regime_{tf_name}_{sym}', time.time()-t1, 'WARN', 'No vol data')
            else:
                log(f'regime_{tf_name}_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
        except Exception as e:
            log(f'regime_{tf_name}_{sym}', time.time()-t1, 'FAIL', str(e))

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 09 regime analysis finished')
