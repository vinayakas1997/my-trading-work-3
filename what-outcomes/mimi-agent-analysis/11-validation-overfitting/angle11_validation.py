"""Angle 11: Validation & Overfitting — MC permutation, bootstrap CI, walk-forward."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from scipy.stats import spearmanr
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

print("=== STEP 0: FETCH REAL RETURNS ===")
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
                returns = df['close'].values.astype(float)
                rets = np.diff(returns) / np.clip(returns[:-1], 1e-10, None)
                all_rets.extend(rets.tolist())
                log(f'fetch_{sym}', time.time()-t0, 'PASS', f'{len(rets)} returns')
    except Exception as e:
        log(f'fetch_{sym}', time.time()-t0, 'FAIL', str(e))

rets = pd.Series(all_rets)

# ── Step 1: Observed Sharpe ──
print("\n=== STEP 1: OBSERVED SHARPE ===")
t0 = time.time()
obs_sr = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0.0
log('obs_sharpe', time.time()-t0, 'PASS', f'SR={obs_sr:.4f}, N={len(rets)}')

# ── Step 2: Monte Carlo Permutation ──
print("\n=== STEP 2: MONTE CARLO PERMUTATION ===")
t0 = time.time()
n_perm = 1000
perm_srs = []
for _ in range(n_perm):
    p = np.random.permutation(rets)
    sr = p.mean() / p.std() * np.sqrt(252) if p.std() > 0 else 0.0
    perm_srs.append(sr)
p_value = (sum(1 for s in perm_srs if s >= obs_sr) + 1) / (n_perm + 1)
perm_mean = np.mean(perm_srs)
perm_std = np.std(perm_srs)
log('mc_permutation', time.time()-t0, 'PASS',
    f'n_perm={n_perm}, obs_SR={obs_sr:.4f}, perm_mean_SR={perm_mean:.4f}, '
    f'perm_std_SR={perm_std:.4f}, p_value={p_value:.4f}')

# ── Step 3: Bootstrap CI ──
print("\n=== STEP 3: BOOTSTRAP CI ===")
t0 = time.time()
n_bs = 1000
bs_srs = []
for _ in range(n_bs):
    b = np.random.choice(rets, len(rets))
    sr = b.mean() / b.std() * np.sqrt(252) if b.std() > 0 else 0.0
    bs_srs.append(sr)
ci_low = np.percentile(bs_srs, 2.5)
ci_high = np.percentile(bs_srs, 97.5)
bs_mean = np.mean(bs_srs)
log('bootstrap_ci', time.time()-t0, 'PASS',
    f'n_bs={n_bs}, mean_SR={bs_mean:.4f}, 95%_CI=[{ci_low:.4f}, {ci_high:.4f}]')

# ── Step 4: Walk-Forward ──
print("\n=== STEP 4: WALK-FORWARD ===")
t0 = time.time()
n_windows = 4
window_size = len(rets) // n_windows
wf_results = []
for i in range(n_windows):
    start = i * window_size
    end = (i + 1) * window_size if i < n_windows - 1 else len(rets)
    w = rets.iloc[start:end]
    sr = w.mean() / w.std() * np.sqrt(252) if w.std() > 0 else 0.0
    ret_total = float((1 + w).prod() - 1)
    wf_results.append({'window': i + 1, 'sharpe': round(sr, 4), 'total_return': round(ret_total, 4)})
    log(f'wf_window_{i+1}', time.time()-t0, 'PASS', f'SR={sr:.4f}, ret={ret_total:.4f}')

sr_values = [r['sharpe'] for r in wf_results]
log('wf_summary', time.time()-t0, 'PASS',
    f'{n_windows} windows, mean_SR={np.mean(sr_values):.4f}, '
    f'std_SR={np.std(sr_values):.4f}, gap={max(sr_values)-min(sr_values):.4f}')

# ── Step 5: Overfitting Verdict ──
print("\n=== STEP 5: OVERFITTING VERDICT ===")
t0 = time.time()
gap = max(sr_values) - min(sr_values)
if gap <= 0.3:
    verdict = 'LOW risk'
elif gap <= 0.5:
    verdict = 'MODERATE risk'
else:
    verdict = 'HIGH risk'
log('overfitting_verdict', time.time()-t0, 'PASS',
    f'Sharpe_gap={gap:.4f}, verdict={verdict}')

# ── Step 6: Deflated Sharpe (basic) ──
print("\n=== STEP 6: BASIC DEFLATED SHARPE ===")
t0 = time.time()
from scipy import stats as scipy_stats
for n_trials in [1, 5, 10, 30, 50, 100]:
    if n_trials <= 1:
        e_max = 0
    else:
        euler = 0.5772156649
        e_max = (1 - euler) * scipy_stats.norm.ppf(1 - 1/n_trials) + euler * scipy_stats.norm.ppf(1 - 1/n_trials * np.exp(-1))
    dsr = scipy_stats.norm.cdf((obs_sr - e_max) * np.sqrt(len(rets) - 1))
    log(f'dsr_{n_trials}trials', time.time()-t0, 'PASS', f'DSR={dsr:.4f}')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 11 validation finished')
