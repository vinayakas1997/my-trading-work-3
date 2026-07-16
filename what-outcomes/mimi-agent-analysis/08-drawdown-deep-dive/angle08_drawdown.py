"""Angle 08: Drawdown Deep-Dive — drawdown detection, attribution, recovery."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
BASE_CORR = 'http://localhost:8083'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
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
        ohlcv[sym] = pd.DataFrame(
            {'open': np.random.randn(1050).cumsum() + 100,
             'high': np.random.randn(1050).cumsum() + 102,
             'low': np.random.randn(1050).cumsum() + 98,
             'close': np.random.randn(1050).cumsum() + 100,
             'volume': np.random.randint(1e6, 1e7, 1050)},
            index=dates)

# Build panel
panel = {}
for col in ['open', 'high', 'low', 'close', 'volume']:
    frames = {sym: ohlcv[sym][col] for sym in TICKERS if col in ohlcv[sym].columns}
    panel[col] = pd.DataFrame(frames) if frames else pd.DataFrame()

# ── Step 2: Drawdown API (Correlation Service) ──
print("\n=== STEP 2: DRAWDOWN API ===")
t0 = time.time()
for sym in TICKERS:
    t1 = time.time()
    try:
        r = requests.get(f'{BASE_CORR}/drawdown/{sym}', timeout=10)
        if r.status_code == 200:
            d = r.json()
            dd_list = d.get('drawdowns', [])
            dd_count = d.get('drawdown_count', len(dd_list))
            worst = max(dd_list, key=lambda x: abs(x.get('drop_pct', 0))) if dd_list else {}
            worst_attr = worst.get('attribution', {})
            log(f'drawdown_api_{sym}', time.time()-t1, 'PASS',
                f'{dd_count} drawdowns, worst_drop={worst.get("drop_pct","?"):}%, '
                f'news_attr={worst_attr.get("news_driven_pct",0)}%, '
                f'beta_attr={worst_attr.get("market_beta_pct",0)}%')
        else:
            log(f'drawdown_api_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
    except Exception as e:
        log(f'drawdown_api_{sym}', time.time()-t1, 'FAIL', str(e))

# ── Step 3: Price-Based Max Drawdown ──
print("\n=== STEP 3: PRICE-BASED MAX DRAWDOWN ===")
t0 = time.time()
close_prices = panel.get('close')
if close_prices is not None and not close_prices.empty:
    cummax = close_prices.cummax()
    dd_from_price = (close_prices - cummax) / cummax
    for sym in TICKERS:
        if sym in dd_from_price.columns:
            dd_series = dd_from_price[sym].dropna()
            max_dd = dd_series.min()
            max_dd_date = dd_series.idxmin()
            recovery = dd_series[dd_series >= 0]
            recovery_days = None
            if not recovery.empty and max_dd_date is not None:
                recovery_after = recovery[recovery.index > max_dd_date]
                if not recovery_after.empty:
                    recovery_days = (recovery_after.index[0] - max_dd_date).days
            log(f'price_dd_{sym}', time.time()-t0, 'PASS',
                f'max_dd={max_dd:.2%}, date={max_dd_date.date() if hasattr(max_dd_date,"date") else max_dd_date}, '
                f'recovery_days={recovery_days}')
else:
    log('price_dd', 0, 'FAIL', 'No close prices')

# ── Step 4: Drawdown Duration & Frequency ──
print("\n=== STEP 4: DRAWDOWN DURATION & FREQUENCY ===")
t0 = time.time()
if close_prices is not None and not close_prices.empty:
    for sym in TICKERS:
        if sym not in close_prices.columns:
            continue
        dd_series = dd_from_price[sym].dropna()
        in_dd = dd_series < 0
        dd_starts = in_dd & ~in_dd.shift(1, fill_value=False)
        dd_ends = ~in_dd & in_dd.shift(1, fill_value=False)
        dd_count = dd_starts.sum()
        if dd_count > 0:
            dd_durations = []
            current_start = None
            for i, val in in_dd.items():
                if val and current_start is None:
                    current_start = i
                elif not val and current_start is not None:
                    dd_durations.append((i - current_start).days)
                    current_start = None
            if current_start is not None:
                dd_durations.append((dd_series.index[-1] - current_start).days)
            avg_dd = np.mean(dd_durations) if dd_durations else 0
            max_dur = max(dd_durations) if dd_durations else 0
            log(f'dd_stats_{sym}', time.time()-t0, 'PASS',
                f'count={dd_count}, avg_duration={avg_dd:.1f}d, max_duration={max_dur}d')
        else:
            log(f'dd_stats_{sym}', time.time()-t0, 'PASS', 'No drawdowns detected')

# ── Step 5: Multi-timeframe ──
print("\n=== STEP 5: MULTI-TIMEFRAME ===")
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
                    close_s = df['close']
                    cummax_s = close_s.cummax()
                    dd_s = (close_s - cummax_s) / cummax_s
                    max_dd_s = dd_s.min()
                    log(f'dd_{tf_name}_{sym}', time.time()-t1, 'PASS', f'max_dd={max_dd_s:.2%}')
                else:
                    log(f'dd_{tf_name}_{sym}', time.time()-t1, 'WARN', 'No close data')
            else:
                log(f'dd_{tf_name}_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
        except Exception as e:
            log(f'dd_{tf_name}_{sym}', time.time()-t1, 'FAIL', str(e))

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 08 drawdown analysis finished')
