"""Angle 14: Decay Monitoring — IC ratio, rolling IR, health scoring."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

from datetime import datetime, timezone

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

np.random.seed(42)
N = 500

# ── Step 1: IC Computation ──
print("=== STEP 1: IC COMPUTATION ===")
t0 = time.time()
preds = pd.Series(np.random.randn(N))
actuals = pd.Series(preds * 0.05 + np.random.randn(N) * 0.01)
ic_series = preds.rolling(60).corr(actuals).dropna()
ic_mean = ic_series.mean()
ic_std = ic_series.std()
ic_pos_pct = (ic_series > 0).mean()
ic_sharpe = ic_mean / ic_std if ic_std > 0 else 0
log('ic_computation', time.time()-t0, 'PASS',
    f'ic_mean={ic_mean:.4f}, ic_std={ic_std:.4f}, ic_pos_pct={ic_pos_pct:.2%}, '
    f'ic_sharpe={ic_sharpe:.4f}')

# ── Step 2: Rolling Information Ratio ──
print("\n=== STEP 2: ROLLING INFORMATION RATIO ===")
t0 = time.time()
roll_ir = ic_series.rolling(20).mean() / ic_series.rolling(20).std()
roll_ir_mean = roll_ir.mean()
roll_ir_std = roll_ir.std()
roll_ir_pos = (roll_ir > 0).mean()
log('rolling_ir', time.time()-t0, 'PASS',
    f'ir_mean={roll_ir_mean:.4f}, ir_std={roll_ir_std:.4f}, ir_pos_pct={roll_ir_pos:.2%}')

# ── Step 3: Health Score ──
print("\n=== STEP 3: HEALTH SCORE ===")
t0 = time.time()
score = 0
score += 2 if ic_mean > 0 else -2
score += 1 if ic_std < 0.5 else -1
score += 2 if ic_pos_pct > 0.5 else -2
score += 1 if roll_ir_mean > 0 else -1
score += 1 if roll_ir_pos > 0.5 else -1
if score >= 3:
    status = 'HEALTHY'
elif score >= 0:
    status = 'WARNING'
elif score >= -5:
    status = 'DECAYED'
else:
    status = 'CRITICAL'
log('health_score', time.time()-t0, 'PASS', f'score={score}, status={status}')

# ── Step 4: IC Decay Curve ──
print("\n=== STEP 4: IC DECAY CURVE ===")
t0 = time.time()
decay_windows = [10, 20, 40, 60, 120]
for w in decay_windows:
    ic_w = preds.rolling(w).corr(actuals).dropna()
    mean_ic = ic_w.mean()
    log(f'decay_w{w}', time.time()-t0, 'PASS', f'ic_mean={mean_ic:.4f}, n={len(ic_w)}')

# ── Step 5: Benchmark IC Baseline ──
print("\n=== STEP 5: IC BASELINE COMPARISON ===")
t0 = time.time()
baseline_ic = float(np.random.randn() * 0.02)  # simulated baseline
current_ic = ic_mean
ic_ratio = current_ic / baseline_ic if abs(baseline_ic) > 0.01 else 0
log('ic_baseline', time.time()-t0, 'PASS',
    f'baseline_ic={baseline_ic:.4f}, current_ic={current_ic:.4f}, ic_ratio={ic_ratio:.4f}')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 14 decay monitoring finished')
