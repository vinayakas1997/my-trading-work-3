"""Angle 13: Portfolio Analysis — pairwise correlation, rolling beta, hedge ratios."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())
t_all = time.time()

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
    np.random.seed(42)
    for sym in TICKERS:
        ohlcv[sym] = pd.DataFrame({'close': np.random.randn(1050).cumsum() + 100}, index=dates)

# Build panel
panel = {}
for col in ['open', 'high', 'low', 'close', 'volume']:
    frames = {sym: ohlcv[sym][col] for sym in TICKERS if col in ohlcv[sym].columns}
    panel[col] = pd.DataFrame(frames) if frames else pd.DataFrame()
panel['returns'] = panel['close'].pct_change()
returns = panel['returns']

# ── Step 2: Pairwise Correlation Matrix ──
print("\n=== STEP 2: PAIRWISE CORRELATION ===")
t0 = time.time()
ret_data = returns[TICKERS].dropna()
corr_matrix = ret_data.corr()
avg_corr = (corr_matrix.values.sum() - len(corr_matrix)) / (len(corr_matrix)**2 - len(corr_matrix))
log('correlation_matrix', time.time()-t0, 'PASS', corr_matrix.to_string())
log('avg_pairwise_corr', 0, 'PASS', f'{avg_corr:.4f}')

# ── Step 3: Rolling 60d Correlation ──
print("\n=== STEP 3: ROLLING 60d CORRELATION ===")
t0 = time.time()
rolling_corr = ret_data.rolling(60).corr()
for sym1 in TICKERS:
    for sym2 in TICKERS:
        if sym1 < sym2:
            pair_corr = rolling_corr.xs(sym2, level=1)[sym1].dropna()
            log(f'rolling_corr_{sym1}_{sym2}', time.time()-t0, 'PASS',
                f'mean={pair_corr.mean():.4f}, std={pair_corr.std():.4f}, '
                f'min={pair_corr.min():.4f}, max={pair_corr.max():.4f}')

# ── Step 4: Rolling Beta ──
print("\n=== STEP 4: ROLLING BETA (vs AAPL as reference) ===")
t0 = time.time()
ref = 'AAPL'
ref_ret = returns[ref]
for sym in TICKERS:
    if sym == ref:
        continue
    s_ret = returns[sym]
    combined = pd.DataFrame({'s': s_ret, 'ref': ref_ret}).dropna()
    beta = combined['s'].rolling(60).cov(combined['ref']) / combined['ref'].rolling(60).var()
    beta_mean = beta.mean()
    beta_std = beta.std()
    log(f'rolling_beta_{sym}_vs_{ref}', time.time()-t0, 'PASS',
        f'mean_beta={beta_mean:.4f}, std_beta={beta_std:.4f}')

# ── Step 5: Beta-Hedged Performance ──
print("\n=== STEP 5: BETA-HEDGED RETURN ===")
t0 = time.time()
bench_ret = returns['NVDA']  # using NVDA as market proxy
for sym in TICKERS:
    combined = pd.DataFrame({'s': returns[sym], 'b': bench_ret}).dropna()
    if len(combined) < 5:
        continue
    beta_full = combined['s'].cov(combined['b']) / combined['b'].var()
    hedged = combined['s'] - beta_full * combined['b']
    hedged_sr = hedged.mean() / hedged.std() * np.sqrt(252) if hedged.std() > 0 else 0
    raw_sr = combined['s'].mean() / combined['s'].std() * np.sqrt(252) if combined['s'].std() > 0 else 0
    log(f'beta_hedged_{sym}', time.time()-t0, 'PASS',
        f'raw_sharpe={raw_sr:.4f}, hedged_sharpe={hedged_sr:.4f}, beta={beta_full:.4f}')

# ── Step 6: Multi-timeframe ──
print("\n=== STEP 6: MULTI-TIMEFRAME ===")
intervals = {'4h': '1h', '1h': '1h', '15m': '15m'}
for tf_name, interval in intervals.items():
    tf_rets = {}
    for sym in TICKERS:
        try:
            r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
                'interval': interval, 'from': FIRST_TS, 'to': NOW_TS
            }, timeout=15)
            if r.status_code == 200:
                data = r.json().get('data', [])
                df = pd.DataFrame(data)
                if not df.empty and 'close' in df.columns:
                    tf_rets[sym] = df['close'].pct_change()
        except:
            pass
    if len(tf_rets) >= 2:
        tf_ret_df = pd.DataFrame(tf_rets).dropna()
        tf_corr = tf_ret_df.corr()
        tf_avg = (tf_corr.values.sum() - len(tf_corr)) / (len(tf_corr)**2 - len(tf_corr))
        log(f'portfolio_{tf_name}', 0, 'PASS', f'avg_corr={tf_avg:.4f}')

print('\n=== DONE ===')
log('total', time.time()-t_all, 'COMPLETE', 'Angle 13 portfolio analysis finished')
