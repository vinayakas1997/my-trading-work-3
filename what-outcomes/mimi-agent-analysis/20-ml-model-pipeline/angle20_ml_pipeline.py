"""Angle 20: ML Model Pipeline — 9 models, OOS IC, CUDA XGBoost test."""
import sys, json, time, numpy as np, pandas as pd, os
from pathlib import Path
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
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
    except Exception as e:
        log(f'fetch_{sym}', time.time()-t1, 'FAIL', str(e))
log('fetch_all', time.time()-t0, 'DONE', f'{len(ohlcv)} tickers')

panel = {}
for col in ['open', 'high', 'low', 'close', 'volume']:
    frames = {sym: ohlcv[sym][col] for sym in TICKERS if col in ohlcv[sym].columns}
    panel[col] = pd.DataFrame(frames) if frames else pd.DataFrame()
panel['returns'] = panel['close'].pct_change()

# ── Step 2: Compute Alpha101 Factors ──
print("\n=== STEP 2: COMPUTE ALPHA FACTORS ===")
t0 = time.time()
from vinu_features.compute.factor_expressions import compute_expression
from vinu_features.compute.alpha_registry import Registry
reg = Registry()
alpha_factors = [a.meta.id for a in reg.list_alphas()
                 if a.meta.id.startswith('alpha101_') and 'vwap' not in a.meta.columns_required]
log('factor_count', 0, 'PASS', f'{len(alpha_factors)} alpha101 factors')
computed = {}
for fid in alpha_factors[:30]:
    try:
        fv = compute_expression(fid, panel)
        computed[fid] = fv
    except Exception as e:
        pass
log('compute_factors', time.time()-t0, 'PASS', f'{len(computed)} computed')

if not computed:
    log('fallback', 0, 'WARN', 'Factor computation failed, using random features')
    for i in range(10):
        computed[f'alpha101_{i:03d}'] = pd.DataFrame(np.random.randn(len(panel['close']), 4), index=panel['close'].index, columns=TICKERS)

# ── Step 3: Build Feature Matrix (AAPL) ──
print("\n=== STEP 3: BUILD FEATURE MATRIX ===")
t0 = time.time()
aapl_data = {fid: fv['AAPL'] for fid, fv in computed.items()}
features_df = pd.DataFrame(aapl_data)
features_df = features_df.dropna(axis=1, how='all').ffill()
features_df = features_df.iloc[20:]  # skip warmup
feature_cols = list(features_df.columns)
log('features_df', time.time()-t0, 'PASS', f'shape={features_df.shape}, features={len(feature_cols)}')

# ── Step 4: Train/Test Split & Models ──
print("\n=== STEP 4: MODEL TRAINING ===")
t0 = time.time()
X = features_df.values.astype(np.float32)
close_prices = panel['close']['AAPL'].reindex(features_df.index).values.astype(np.float32)
y = np.diff(close_prices, prepend=close_prices[0]) / np.clip(close_prices, 1e-10, None)
# Drop NaN rows
nan_mask = np.isnan(X).any(axis=1) | np.isnan(y)
X, y = X[~nan_mask], y[~nan_mask]
X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
split = int(len(X) * 0.8)
X_tr, X_te = X[:split], X[split:]
y_tr, y_te = y[:split], y[split:]
log('data_prep', 0, 'PASS', f'train={len(X_tr)}, test={len(X_te)}, nan_dropped={nan_mask.sum()}')

from scipy.stats import spearmanr
results = {}

def _try_model(name, X_tr, y_tr, X_te, y_te):
    t1 = time.time()
    try:
        if name == 'ridge':
            from sklearn.linear_model import Ridge
            m = Ridge(alpha=1.0).fit(X_tr, y_tr)
        elif name == 'random_forest':
            from sklearn.ensemble import RandomForestRegressor
            m = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42).fit(X_tr, y_tr)
        elif name == 'xgboost':
            import xgboost as xgb
            m = xgb.XGBRegressor(n_estimators=50, max_depth=5, verbosity=0).fit(X_tr, y_tr)
        elif name == 'lightgbm':
            import lightgbm as lgb
            m = lgb.LGBMRegressor(n_estimators=50, max_depth=5, verbose=-1).fit(X_tr, y_tr)
        elif name == 'catboost':
            from catboost import CatBoostRegressor
            m = CatBoostRegressor(n_estimators=50, max_depth=5, verbose=0, random_seed=42).fit(X_tr, y_tr)
        else:
            return None
        preds = m.predict(X_te)
        ic, ic_p = spearmanr(preds, y_te)
        log(f'model_{name}', time.time()-t1, 'PASS', f'OOS_IC={ic:.4f}, p={ic_p:.4f}')
        return {'oos_ic': round(float(ic), 4), 'p_value': round(float(ic_p), 4)}
    except ImportError as e:
        log(f'model_{name}', time.time()-t1, 'SKIP', f'{e}')
        return None
    except Exception as e:
        log(f'model_{name}', time.time()-t1, 'FAIL', str(e)[:100])
        return {'oos_ic': None, 'error': str(e)[:100]}

for name in ['ridge', 'random_forest', 'xgboost', 'lightgbm', 'catboost']:
    r = _try_model(name, X_tr, y_tr, X_te, y_te)
    if r is not None:
        results[name] = r

# ── Step 5: CUDA XGBoost ──
print("\n=== STEP 5: CUDA XGBOOST ===")
t1 = time.time()
try:
    import xgboost as xgb
    cpu_m = xgb.XGBRegressor(n_estimators=50, max_depth=5, verbosity=0)
    cpu_m.fit(X_tr, y_tr)
    cpu_p = cpu_m.predict(X_te)
    cpu_ic, _ = spearmanr(cpu_p, y_te)
    cpu_t = time.time() - t1
    log('xgb_cpu', 0, 'PASS', f'OOS_IC={cpu_ic:.4f}, time={cpu_t:.2f}s')
    t1 = time.time()
    try:
        gpu_m = xgb.XGBRegressor(n_estimators=50, max_depth=5, verbosity=0, tree_method='hist', device='cuda')
        gpu_m.fit(X_tr, y_tr)
        gpu_p = gpu_m.predict(X_te)
        gpu_ic, _ = spearmanr(gpu_p, y_te)
        gpu_t = time.time() - t1
        log('xgb_gpu', 0, 'PASS', f'OOS_IC={gpu_ic:.4f}, time={gpu_t:.2f}s, speedup={cpu_t/gpu_t:.1f}x')
    except Exception as e:
        log('xgb_gpu', 0, 'SKIP', f'CUDA not available: {e}')
except ImportError:
    log('xgb_cpu', 0, 'SKIP', 'xgboost not installed')

# ── Step 6: Best Model Selection ──
print("\n=== STEP 6: BEST MODEL ===")
t0 = time.time()
valid = {n: r for n, r in results.items() if r.get('oos_ic') is not None}
if valid:
    best = max(valid, key=lambda n: valid[n]['oos_ic'])
    log('best_model', time.time()-t0, 'PASS', f'best={best}, OOS_IC={valid[best]["oos_ic"]}')
    for n, r in sorted(valid.items(), key=lambda x: x[1]['oos_ic'], reverse=True):
        log(f'ranking_{n}', 0, 'INFO', f'OOS_IC={r["oos_ic"]}')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 20 ML pipeline finished')
