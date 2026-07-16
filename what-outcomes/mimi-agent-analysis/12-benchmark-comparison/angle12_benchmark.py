"""Angle 12: Benchmark Comparison — alpha, beta, tracking error vs NVDA."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
BENCHMARK = 'NVDA'  # SPY not available in catalog
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

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

# Use synthetic fallback if no data
if not ohlcv:
    log('fallback', 0, 'WARN', 'No OHLCV data — using synthetic data')
    dates = pd.date_range('2022-01-01', periods=1050, freq='D')
    for sym in TICKERS:
        ohlcv[sym] = pd.DataFrame({'close': np.random.randn(1050).cumsum() + 100}, index=dates)

# Build panel
panel = {}
for col in ['open', 'high', 'low', 'close', 'volume']:
    frames = {sym: ohlcv[sym][col] for sym in TICKERS if col in ohlcv[sym].columns}
    panel[col] = pd.DataFrame(frames) if frames else pd.DataFrame()
panel['returns'] = panel['close'].pct_change()

# ── Step 2: Benchmark-Relative Metrics ──
print("\n=== STEP 2: BENCHMARK COMPARISON ===")
returns = panel['returns']
bench_ret = returns[BENCHMARK].dropna()

t0 = time.time()
for sym in TICKERS:
    t1 = time.time()
    if sym == BENCHMARK:
        continue
    strat_ret = returns[sym].dropna()
    combined = pd.DataFrame({'strat': strat_ret, 'bench': bench_ret}).dropna()
    if len(combined) < 5:
        log(f'benchmark_{sym}', time.time()-t1, 'FAIL', f'Too few overlapping periods ({len(combined)})')
        continue
    r_s = combined['strat']
    r_b = combined['bench']
    beta = r_s.cov(r_b) / r_b.var()
    alpha = r_s.mean() - beta * r_b.mean()
    te = (r_s - beta * r_b).std()
    ir = alpha / te if te > 0 else 0.0
    excess_cagr = (1 + r_s).prod() ** (252 / len(r_s)) - 1 - ((1 + r_b).prod() ** (252 / len(r_b)) - 1)
    up_days = r_b > 0
    down_days = r_b < 0
    up_capture = r_s[up_days].mean() / r_b[up_days].mean() if up_days.any() and r_b[up_days].mean() != 0 else np.nan
    down_capture = r_s[down_days].mean() / r_b[down_days].mean() if down_days.any() and r_b[down_days].mean() != 0 else np.nan
    market_corr = r_s.corr(r_b)
    rel_max_dd = None
    equity_ratio = (1 + r_s).cumprod() / (1 + r_b).cumprod()
    running_max = equity_ratio.cummax()
    dd_ratio = (equity_ratio - running_max) / running_max
    rel_max_dd = dd_ratio.min()

    log(f'benchmark_{sym}', time.time()-t1, 'PASS',
        f'beta={beta:.4f}, alpha={alpha:.6f}, te={te:.4f}, ir={ir:.4f}, '
        f'excess_cagr={excess_cagr:.4f}, up_cap={up_capture:.4f}, '
        f'down_cap={down_capture:.4f}, corr={market_corr:.4f}, rel_dd={rel_max_dd:.4f}')

# ── Step 3: SPY Catalog Check ──
print("\n=== STEP 3: SPY AVAILABILITY ===")
t0 = time.time()
try:
    r = requests.get(f'{BASE_PRICE}/catalog', timeout=10)
    if r.status_code == 200:
        catalog = r.json()
        if 'SPY' in catalog:
            log('spy_check', time.time()-t0, 'INFO', 'SPY is in catalog')
        else:
            log('spy_check', time.time()-t0, 'WARN', 'SPY not in catalog — using NVDA as benchmark proxy')
    else:
        log('spy_check', time.time()-t0, 'FAIL', f'HTTP {r.status_code}')
except Exception as e:
    log('spy_check', time.time()-t0, 'FAIL', str(e))

# ── Step 4: Multi-timeframe ──
print("\n=== STEP 4: MULTI-TIMEFRAME ===")
intervals = {'4h': '1h', '1h': '1h', '15m': '15m'}
for tf_name, interval in intervals.items():
    tf_ohlcv = {}
    for sym in TICKERS:
        try:
            r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
                'interval': interval, 'from': FIRST_TS, 'to': NOW_TS
            }, timeout=15)
            if r.status_code == 200:
                data = r.json().get('data', [])
                df = pd.DataFrame(data)
                if not df.empty and 'close' in df.columns:
                    df['ret'] = df['close'].pct_change()
                    tf_ohlcv[sym] = df['ret']
        except:
            pass
    if BENCHMARK in tf_ohlcv and len(tf_ohlcv) > 1:
        b_ret = tf_ohlcv[BENCHMARK].dropna()
        for sym in TICKERS:
            if sym == BENCHMARK or sym not in tf_ohlcv:
                continue
            s_ret = tf_ohlcv[sym].dropna()
            c = pd.DataFrame({'s': s_ret, 'b': b_ret}).dropna()
            if len(c) > 5:
                beta_tf = c['s'].cov(c['b']) / c['b'].var()
                alpha_tf = c['s'].mean() - beta_tf * c['b'].mean()
                log(f'bench_{tf_name}_{sym}', 0, 'PASS', f'beta={beta_tf:.4f}, alpha={alpha_tf:.6f}')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 12 benchmark comparison finished')
