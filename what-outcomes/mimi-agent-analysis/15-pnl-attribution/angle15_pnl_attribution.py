"""Angle 15: PnL Attribution — decompose PnL into core, noise, early/late exit."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

from datetime import datetime, timezone

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

np.random.seed(42)

# ── Step 1: Generate Synthetic Trades ──
print("=== STEP 1: SYNTHETIC TRADES ===")
t0 = time.time()
n_trades = 200
trades = pd.DataFrame({
    'pnl': np.random.randn(n_trades) * 0.02 + 0.002,
    'holding_days': np.random.exponential(5, n_trades),
    'exit_reason': np.random.choice(['take_profit', 'stop_loss', 'time_exit', 'signal_exit'], n_trades),
})
log('synthetic_trades', time.time()-t0, 'PASS', f'{len(trades)} trades generated')

# ── Step 2: Total PnL ──
print("\n=== STEP 2: TOTAL PNL ===")
t0 = time.time()
total_pnl = trades['pnl'].sum()
total_pnl_pct = (1 + trades['pnl']).prod() - 1
log('total_pnl', time.time()-t0, 'PASS', f'total_pnl={total_pnl:.4f}, total_return={total_pnl_pct:.4f}')

# ── Step 3: Core vs Noise PnL ──
print("\n=== STEP 3: CORE VS NOISE PNL ===")
t0 = time.time()
threshold = trades['pnl'].abs().quantile(0.75)
noise_threshold = trades['pnl'].abs().quantile(0.25)
core = trades[trades['pnl'].abs() <= threshold]['pnl'].sum()
noise = trades[trades['pnl'].abs() <= noise_threshold]['pnl'].sum()
large = trades[trades['pnl'].abs() > threshold]['pnl'].sum()
log('core_pnl', time.time()-t0, 'PASS', f'core={core:.4f}, noise={noise:.4f}, large_moves={large:.4f}')

# ── Step 4: Early vs Late Exit PnL ──
print("\n=== STEP 4: EXIT TIMING PNL ===")
t0 = time.time()
mean_hold = trades['holding_days'].mean()
std_hold = trades['holding_days'].std()
early = trades[trades['holding_days'] < (mean_hold - std_hold)]['pnl'].sum()
late = trades[trades['holding_days'] > (mean_hold + std_hold)]['pnl'].sum()
normal = trades[(trades['holding_days'] >= mean_hold - std_hold) & (trades['holding_days'] <= mean_hold + std_hold)]['pnl'].sum()
log('exit_timing', time.time()-t0, 'PASS',
    f'early_exit={early:.4f}, late_exit={late:.4f}, normal_exit={normal:.4f}, '
    f'mean_hold={mean_hold:.2f}d, std_hold={std_hold:.2f}d')

# ── Step 5: Exit Reason Attribution ──
print("\n=== STEP 5: EXIT REASON ATTRIBUTION ===")
t0 = time.time()
for reason in trades['exit_reason'].unique():
    grp = trades[trades['exit_reason'] == reason]
    pnl = grp['pnl'].sum()
    count = len(grp)
    win_rate = (grp['pnl'] > 0).mean()
    log(f'exit_{reason}', time.time()-t0, 'PASS',
        f'pnl={pnl:.4f}, count={count}, win_rate={win_rate:.2%}')

# ── Step 6: Overtrading Penalty ──
print("\n=== STEP 6: OVERTRADING ANALYSIS ===")
t0 = time.time()
max_trades = 20
n_periods = 50
trades_per_period = len(trades) / n_periods
if trades_per_period > max_trades:
    overtrading_penalty = (trades_per_period - max_trades) * 0.001
    log('overtrading', time.time()-t0, 'WARN',
        f'trades_per_period={trades_per_period:.1f}, penalty={overtrading_penalty:.4f}')
else:
    log('overtrading', time.time()-t0, 'PASS',
        f'trades_per_period={trades_per_period:.1f}, no penalty')

# ── Step 7: Decomposition Summary ──
print("\n=== STEP 7: DECOMPOSITION SUMMARY ===")
t0 = time.time()
decomp = {
    'total_pnl': float(round(total_pnl, 4)),
    'core_pnl': float(round(core, 4)),
    'noise_pnl': float(round(noise, 4)),
    'large_move_pnl': float(round(large, 4)),
    'early_exit_pnl': float(round(early, 4)),
    'late_exit_pnl': float(round(late, 4)),
    'normal_exit_pnl': float(round(normal, 4)),
}
log('decomposition', time.time()-t0, 'PASS', str(decomp))

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 15 PnL attribution finished')
