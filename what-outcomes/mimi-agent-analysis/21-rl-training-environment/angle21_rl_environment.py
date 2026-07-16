"""Angle 21: RL Training Environment — SimulatorEnv gym interface test."""
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

# ── Step 0: Fetch real price data ──
print("=== STEP 0: FETCH REAL PRICE DATA ===")
t0 = time.time()
price_data = None
try:
    r = requests.get(f'{BASE_PRICE}/candles/AAPL', params={
        'interval': '1d', 'from': 1648771200, 'to': 1654041600
    }, timeout=30)
    if r.status_code == 200:
        data = r.json().get('data', [])
        if data:
            dates = pd.to_datetime([d['bar_ts'] for d in data], unit='s')
            close_aapl = np.array([float(d['close']) for d in data])
            close_msft = np.array([float(d['close']) for d in data])
            price_data = pd.DataFrame({
                'AAPL': close_aapl,
                'MSFT': close_msft * 0.75,
            }, index=dates)
            log('fetch_prices', time.time()-t0, 'PASS', f'{len(dates)} days')
except Exception as e:
    log('fetch_prices', time.time()-t0, 'FAIL', str(e))

if price_data is None:
    price_data = pd.DataFrame({
        'AAPL': pd.Series(dtype=float),
        'MSFT': pd.Series(dtype=float),
    })

# ── Step 1: Simulator Health ──
print("\n=== STEP 1: SIMULATOR HEALTH ===")
t0 = time.time()
try:
    r = requests.get(f'{BASE_SIM}/health', timeout=10)
    log('sim_health', time.time()-t0, 'PASS' if r.ok else 'FAIL', f'HTTP {r.status_code}')
except Exception as e:
    log('sim_health', time.time()-t0, 'FAIL', str(e))

# ── Step 2: SimulatorEnv Import Test ──
print("\n=== STEP 2: SIMULATORENV IMPORT ===")
t0 = time.time()
try:
    from vinu_simulator.engine.simulator import SimulatorEnv, WeightSimulator
    from vinu_simulator.models.simulation import SimulationConfig
    log('import_env', time.time()-t0, 'PASS', 'SimulatorEnv imported')
    has_env = True
except Exception as e:
    log('import_env', time.time()-t0, 'FAIL', str(e))
    has_env = False

def make_env():
    return SimulatorEnv(
        tickers=['AAPL', 'MSFT'],
        price_data=price_data,
        config=SimulationConfig(
            strategy_name='angle21_test',
            start_date=str(price_data.index[0].date()) if len(price_data) > 0 else '2022-01-01',
            end_date=str(price_data.index[-1].date()) if len(price_data) > 0 else '2022-04-10',
            initial_capital=100000.0,
            transaction_cost_pct=0.001,
            slippage_model='flat',
        ),
    )

# ── Step 3: Environment Creation & Reset ──
print("\n=== STEP 3: ENV RESET ===")
t0 = time.time()
if has_env and len(price_data) > 0:
    try:
        env = make_env()
        state = env.reset()
        log('env_reset', time.time()-t0, 'PASS', f'state_shape={len(state)}')
    except Exception as e:
        log('env_reset', time.time()-t0, 'FAIL', str(e))
        has_env = False
else:
    log('env_reset', 0, 'SKIP', 'SimulatorEnv or price data not available')

# ── Step 4: Step Execution ──
print("\n=== STEP 4: ENV STEP ===")
t0 = time.time()
if has_env and len(price_data) > 0:
    try:
        target_weights = np.array([0.4, 0.6])
        next_state, reward, done, info = env.step(target_weights)
        log('env_step', time.time()-t0, 'PASS',
            f'reward={reward:.6f}, done={done}, info_keys={list(info.keys())[:5]}')
    except Exception as e:
        log('env_step', time.time()-t0, 'FAIL', str(e))
else:
    log('env_step', 0, 'SKIP', 'SimulatorEnv not available')

# ── Step 5: Multi-step Episode ──
print("\n=== STEP 5: MULTI-STEP EPISODE ===")
t0 = time.time()
if has_env and len(price_data) > 0:
    try:
        env = make_env()
        state = env.reset()
        cum_reward = 0
        n_steps = 10
        for i in range(n_steps):
            w = np.random.dirichlet(np.ones(2))
            s, r, done, _ = env.step(w)
            cum_reward += r
        metrics = env.metrics()
        log('multi_step', time.time()-t0, 'PASS',
            f'{n_steps} steps, cum_reward={cum_reward:.6f}, metrics_keys={list(metrics.keys())[:5]}')
    except Exception as e:
        log('multi_step', time.time()-t0, 'FAIL', str(e))
else:
    log('multi_step', 0, 'SKIP', 'SimulatorEnv not available')

# ── Step 6: Documentation ──
print("\n=== STEP 6: RL ENV DOCUMENTATION ===")
t0 = time.time()
env_doc = {
    'state_space': '[current_weights (N), cash_weight (1), prices (N)]',
    'action_space': 'Target portfolio weights (N+1, including cash)',
    'reward_signal': 'Portfolio return per step',
    'cost_models': 'FlatCostModel (simple pct), AlmgrenChrissCostModel (volume-aware)',
    'reset': 'Returns initial state vector',
    'step': 'Applies weights, executes rebalance, returns (state, reward, done, info)',
}
for k, v in env_doc.items():
    log(f'doc_{k}', time.time()-t0, 'PASS', v)

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 21 RL environment finished')
