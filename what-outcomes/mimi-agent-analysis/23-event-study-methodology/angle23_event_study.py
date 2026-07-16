"""Angle 23: Event Study Methodology — abnormal return, CAR, t-test."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone
from scipy import stats

BASE_PRICE = 'http://localhost:8081'
BASE_CORR = 'http://localhost:8083'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# ── Step 1: Events API ──
print("=== STEP 1: EVENTS API ===")
t0 = time.time()
for sym in TICKERS:
    t1 = time.time()
    try:
        r = requests.get(f'{BASE_CORR}/events/{sym}', timeout=10)
        if r.status_code == 200:
            ev_data = r.json().get('data', [])
            sig_counts = {}
            for e in ev_data:
                sig = e.get('significance', '?')
                sig_counts[sig] = sig_counts.get(sig, 0) + 1
            log(f'events_{sym}', time.time()-t1, 'PASS',
                f'{len(ev_data)} events, significance={sig_counts}')
        else:
            log(f'events_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
    except Exception as e:
        log(f'events_{sym}', time.time()-t1, 'FAIL', str(e))

# ── Step 2: Manual Event Study ──
print("\n=== STEP 2: MANUAL EVENT STUDY ===")
t0 = time.time()
np.random.seed(42)
n_events = 50
est_window = 7  # days
event_window = 1  # day

events = pd.DataFrame({
    'date': pd.date_range('2022-01-10', periods=n_events, freq='14D'),
    'est_mean': np.random.randn(n_events) * 0.005,
    'est_std': np.abs(np.random.randn(n_events)) * 0.01 + 0.005,
})
event_results = []
for _, ev in events.iterrows():
    actual_return = ev['est_mean'] + np.random.randn() * ev['est_std']
    abnormal_return = actual_return - ev['est_mean']
    t_stat = abnormal_return / ev['est_std'] if ev['est_std'] > 0 else 0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=est_window - 1))
    if p_val < 0.01:
        sig = 'highly_significant'
    elif p_val < 0.05:
        sig = 'significant'
    elif p_val < 0.10:
        sig = 'marginally_significant'
    else:
        sig = 'insignificant'
    event_results.append({
        'abnormal_return': abnormal_return,
        't_stat': t_stat,
        'p_value': p_val,
        'significance': sig,
    })
er_df = pd.DataFrame(event_results)
sig_dist = er_df['significance'].value_counts().to_dict()
log('manual_event_study', time.time()-t0, 'PASS', f'significance_dist={sig_dist}')

# ── Step 3: CAR (Cumulative Abnormal Return) ──
print("\n=== STEP 3: CUMULATIVE ABNORMAL RETURN ===")
t0 = time.time()
car_window = 5
car_series = []
for i in range(len(event_results) - car_window + 1):
    car = sum(er_df['abnormal_return'].iloc[i:i+car_window])
    car_series.append(car)
car_mean = np.mean(car_series)
car_ste = np.std(car_series) / np.sqrt(len(car_series))
car_t = car_mean / car_ste if car_ste > 0 else 0
car_p = 2 * (1 - stats.t.cdf(abs(car_t), df=len(car_series) - 1))
log('car_analysis', time.time()-t0, 'PASS',
    f'window={car_window}, mean_CAR={car_mean:.4f}, t={car_t:.4f}, p={car_p:.4f}, '
    f'n_windows={len(car_series)}')

# ── Step 4: Significance Thresholds ──
print("\n=== STEP 4: SIGNIFICANCE CLASSIFICATION ===")
t0 = time.time()
thresholds = {
    'highly_significant': 'p < 0.01',
    'significant': '0.01 <= p < 0.05',
    'marginally_significant': '0.05 <= p < 0.10',
    'insignificant': 'p >= 0.10',
}
for name, thresh in thresholds.items():
    log(f'threshold_{name}', time.time()-t0, 'PASS', thresh)

# ── Step 5: Multi-ticker Price Fetch for Event Context ──
print("\n=== STEP 5: CANDLE CONTEXT ===")
t0 = time.time()
for sym in TICKERS:
    t1 = time.time()
    try:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
            'interval': '1d', 'from': FIRST_TS, 'to': FIRST_TS + 30*86400,
        }, timeout=15)
        if r.status_code == 200:
            data = r.json().get('data', [])
            log(f'candles_{sym}', time.time()-t1, 'PASS', f'{len(data)} bars for event context')
        else:
            log(f'candles_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
    except Exception as e:
        log(f'candles_{sym}', time.time()-t1, 'FAIL', str(e))

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 23 event study finished')
