"""Angle 22: Deflated Sharpe Ratio — Bailey & Lopez de Prado multiple testing correction."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from scipy import stats
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

def deflated_sharpe(obs_sharpe, n_trials, n_obs, skew=0, kurt=0):
    if n_trials <= 1:
        e_max = 0
    else:
        euler = 0.5772156649
        term1 = (1 - euler) * stats.norm.ppf(1 - 1 / n_trials)
        term2 = euler * stats.norm.ppf(1 - 1 / n_trials * np.exp(-1))
        e_max = term1 + term2
    var_sr = (1 + 0.5 * obs_sharpe**2) / (n_obs - 1)
    if skew != 0 or kurt != 0:
        var_sr = (1 + 0.5 * obs_sharpe**2 - skew * obs_sharpe + (kurt - 3) / 4 * obs_sharpe**2) / (n_obs - 1)
    dsr = stats.norm.cdf((obs_sharpe - e_max) / np.sqrt(var_sr))
    return dsr, e_max

# ── Step 0: Compute real Sharpe from actual returns ──
print("=== STEP 0: COMPUTE REAL SHARPE ===")
t0 = time.time()
all_rets = []
for sym in TICKERS:
    try:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
            'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS
        }, timeout=30)
        if r.status_code == 200:
            data = r.json().get('data', [])
            df = pd.DataFrame(data)
            if not df.empty and 'close' in df.columns:
                close = df['close'].values.astype(float)
                rets = np.diff(close) / np.clip(close[:-1], 1e-10, None)
                all_rets.extend(rets.tolist())
                log(f'fetch_{sym}', time.time()-t0, 'PASS', f'{len(rets)} returns')
    except Exception as e:
        log(f'fetch_{sym}', time.time()-t0, 'FAIL', str(e))

rets = np.array(all_rets)
obs_sr = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0.0
n_obs = len(rets)
log('obs_sharpe', time.time()-t0, 'PASS', f'SR={obs_sr:.4f}, N={n_obs}')

# ── Step 1: Basic DSR (no skew/kurt adjustment) ──
print("\n=== STEP 1: BASIC DSR (varying trials) ===")
t0 = time.time()
for n_trials in [1, 5, 10, 30, 50, 100, 200]:
    dsr, e_max = deflated_sharpe(obs_sr, n_trials, n_obs)
    log(f'dsr_{n_trials}t', time.time()-t0, 'PASS',
        f'trials={n_trials}, E[max_SR]={e_max:.4f}, DSR={dsr:.4f}')

# ── Step 2: DSR with varying Sharpe ──
print("\n=== STEP 2: DSR (varying Sharpe, 30 trials) ===")
t0 = time.time()
n_trials = 30
for sr in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
    dsr, e_max = deflated_sharpe(sr, n_trials, n_obs)
    log(f'dsr_sr{sr:.1f}', time.time()-t0, 'PASS', f'SR={sr:.1f}, E[max]={e_max:.4f}, DSR={dsr:.4f}')

# ── Step 3: DSR with skew/kurt adjustment ──
print("\n=== STEP 3: DSR (skew/kurt adjusted, 30 trials) ===")
t0 = time.time()
n_trials = 30
configs = [
    ('normal', 0, 0),
    ('positive_skew', 0.5, 0),
    ('negative_skew', -0.5, 0),
    ('fat_tails', 0, 3),
    ('skewed_fat', 0.5, 3),
]
for name, skew, kurt in configs:
    dsr, e_max = deflated_sharpe(obs_sr, n_trials, n_obs, skew, kurt)
    log(f'dsr_{name}', time.time()-t0, 'PASS',
        f'skew={skew}, kurt={kurt}, DSR={dsr:.4f}')

# ── Step 4: DSR with varying observations ──
print("\n=== STEP 4: DSR (varying N observations, 30 trials) ===")
t0 = time.time()
n_trials = 30
for n in [50, 100, 250, 500, 1000]:
    dsr, e_max = deflated_sharpe(obs_sr, n_trials, n)
    log(f'dsr_n{n}', time.time()-t0, 'PASS', f'N={n}, DSR={dsr:.4f}')

# ── Step 5: Significance Threshold Analysis ──
print("\n=== STEP 5: SIGNIFICANCE THRESHOLDS ===")
t0 = time.time()
log('thresholds', time.time()-t0, 'INFO',
    'DSR > 0.95 = genuine skill, 0.50-0.95 = uncertain, < 0.50 = likely luck')

for n_trials in [1, 5, 10, 30, 50, 100]:
    dsr, _ = deflated_sharpe(obs_sr, n_trials, n_obs)
    if dsr > 0.95:
        verdict = 'genuine skill'
    elif dsr > 0.50:
        verdict = 'uncertain'
    else:
        verdict = 'likely luck'
    log(f'verdict_{n_trials}t', time.time()-t0, 'PASS', f'{n_trials} trials: DSR={dsr:.4f} → {verdict}')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 22 deflated Sharpe finished')
