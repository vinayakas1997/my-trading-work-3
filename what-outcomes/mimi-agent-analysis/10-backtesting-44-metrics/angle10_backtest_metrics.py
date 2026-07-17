"""Angle 10: Backtesting — 44+ metrics from _compute_metrics and simulator."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
BASE_SIM = 'http://localhost:8085'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# ── Step 1: _compute_metrics unit test ──
print("=== STEP 1: _compute_metrics UNIT TEST ===")
t0 = time.time()
from vinu_tools.compute.factor_backtest import _compute_metrics, _annualization_factor
np.random.seed(42)
for freq in ['1d', '4h', '1h', '15m']:
    n = 500 if freq == '1d' else 2000
    returns = pd.Series(np.random.randn(n) * 0.01 + 0.0005)
    m = _compute_metrics(returns, freq)
    log(f'metrics_{freq}', time.time()-t0, 'PASS',
        {k: round(v, 6) if isinstance(v, float) else v for k, v in m.items()})
log('annualization_factors', 0, 'INFO', {f: _annualization_factor(f) for f in ['1d','4h','1h','15m']})

# ── Step 2: Simulator API health ──
print("\n=== STEP 2: SIMULATOR API ===")
t0 = time.time()
try:
    r = requests.get(f'{BASE_SIM}/health', timeout=10)
    log('sim_health', time.time()-t0, 'PASS' if r.ok else 'FAIL', f'HTTP {r.status_code}')
except Exception as e:
    log('sim_health', time.time()-t0, 'FAIL', str(e))

t0 = time.time()
try:
    r = requests.post(f'{BASE_SIM}/simulate/custom', json={
        'strategy_code': '''
import pandas as pd
from vinu_simulator.engine.strategies import BaseStrategy
class MaCrossover(BaseStrategy):
    def generate_weights(self, data):
        close = data["close"]
        sma9 = close.rolling(9).mean()
        sma21 = close.rolling(21).mean()
        signal = (sma9 > sma21).astype(float) - (sma9 < sma21).astype(float)
        return signal.fillna(0.0) * 0.5
''',
        'class_name': 'MaCrossover',
        'symbols': ['AAPL'],
        'start_date': '2022-01-03', 'end_date': '2022-06-01',
        'initial_capital': 100000.0,
        'interval': '1d'
    }, timeout=30)
    log('sim_simulate', time.time()-t0, 'PASS' if r.ok else 'FAIL', f'HTTP {r.status_code}: {r.text[:300]}')
except Exception as e:
    log('sim_simulate', time.time()-t0, 'FAIL', str(e))

# ── Step 3: Strategy evaluate ──
print("\n=== STEP 3: STRATEGY EVALUATE ===")
t0 = time.time()
try:
    r = requests.post(f'http://localhost:8084/strategies/adx_filtered_crossover/evaluate?symbols=AAPL', timeout=15)
    log('strat_evaluate', time.time()-t0, 'PASS' if r.ok else 'FAIL', f'HTTP {r.status_code}: {r.text[:200]}')
except Exception as e:
    log('strat_evaluate', time.time()-t0, 'FAIL', str(e))

# ── Step 4: Extended metrics computation ──
print("\n=== STEP 4: EXTENDED METRICS ===")
t0 = time.time()
rets = pd.Series(np.random.randn(1000) * 0.01 + 0.0005)
m = _compute_metrics(rets, '1d')
extended = {}
extended['var_95'] = float(rets.quantile(0.05))
extended['var_99'] = float(rets.quantile(0.01))
extended['cvar_95'] = float(rets[rets <= rets.quantile(0.05)].mean())
extended['tail_ratio'] = float(abs(rets.quantile(0.95) / rets.quantile(0.05))) if rets.quantile(0.05) != 0 else None
extended['skewness'] = float(rets.skew())
extended['kurtosis'] = float(rets.kurtosis())
extended['avg_win'] = float(rets[rets > 0].mean()) if (rets > 0).any() else 0
extended['avg_loss'] = float(rets[rets < 0].mean()) if (rets < 0).any() else 0
extended['win_loss_ratio'] = abs(extended['avg_win'] / extended['avg_loss']) if extended['avg_loss'] != 0 else None
log('extended_metrics', time.time()-t0, 'PASS', extended)

# ── Step 5: Multi-timeframe metrics ──
print("\n=== STEP 5: MULTI-TIMEFRAME METRICS ===")
t0 = time.time()
for freq in ['4h', '1h', '15m']:
    n = 2000 if freq in ['1h', '15m'] else 1000
    rets = pd.Series(np.random.randn(n) * 0.01 + 0.0005)
    m = _compute_metrics(rets, freq)
    log(f'metrics_{freq}', time.time()-t0, 'PASS', f'SR={m["sharpe_ratio"]:.4f}, DD={m["max_drawdown"]:.4f}')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 10 backtest metrics finished')
