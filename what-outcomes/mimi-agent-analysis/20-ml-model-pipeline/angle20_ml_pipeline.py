"""Angle 20: Actual ML Pipeline with CUDA — real alpha factors, 9 models, GPU test."""
import sys, json, time, numpy as np, pandas as pd
from pathlib import Path
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')

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
    r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
        'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS
    }, timeout=30)
    df = pd.DataFrame(r.json().get('data', []))
    df['date'] = pd.to_datetime(df['bar_ts'], unit='s')
    df.set_index('date', inplace=True); df.sort_index(inplace=True)
    ohlcv[sym] = df
log('fetch', time.time()-t0, 'DONE', f'{len(ohlcv)} tickers, {len(ohlcv["AAPL"])} bars each')

# ── Step 2: Build Panel & Compute Alpha101 Factors ──
print("=== STEP 2: COMPUTE ALPHA FACTORS ===")
t0 = time.time()
panel = {c: pd.DataFrame({s: ohlcv[s][c] for s in TICKERS}) for c in ['open','high','low','close','volume']}
panel['returns'] = panel['close'].pct_change()

from vinu_features.compute.factor_expressions import compute_expression, list_expression_variables

# Get all alpha101 factor IDs (only those that don't need VWAP)
from vinu_features.compute.alpha_registry import Registry
reg = Registry()
alpha_factors = [a.meta.id for a in reg.list_alphas()
                 if a.meta.id.startswith('alpha101_') and 'vwap' not in a.meta.columns_required]
log('factor_count', 0, 'PASS', f'{len(alpha_factors)} alpha101 factors (no VWAP required)')

# Compute them
computed = {}
failed = []
for fid in alpha_factors:
    try:
        fv = compute_expression(fid, panel)
        computed[fid] = fv
    except Exception as e:
        failed.append((fid, str(e)[:50]))

log('compute_factors', time.time()-t0, 'PASS', f'{len(computed)} computed, {len(failed)} failed')
if failed:
    log('compute_failures', 0, 'INFO', f'Failed: {failed[:5]}...')

# ── Step 3: Build Features DataFrame ──
print("=== STEP 3: BUILD FEATURES DATAFRAME ===")
t0 = time.time()
# Convert to long format: Align all factor values by date and ticker
# Use AAPL as the primary (single-ticker ML)
aapl_factors = {fid: fv['AAPL'] for fid, fv in computed.items()}
features_df = pd.DataFrame(aapl_factors)
features_df['close'] = panel['close']['AAPL']
# Drop columns that are entirely NaN
features_df = features_df.dropna(axis=1, how='all')
# Forward-fill and drop initial warmup rows
features_df = features_df.ffill()
features_df = features_df.iloc[252:]  # Skip 1 year warmup
features_df = features_df.reset_index(drop=False)
feature_cols = [c for c in features_df.columns if c.startswith('alpha101_')]
log('features_df', time.time()-t0, 'PASS' if len(features_df) > 200 else 'FAIL',
    f'shape={features_df.shape}, features={len(feature_cols)}')

# ── Step 4: Save as Parquet & Run ML Pipeline ──
print("=== STEP 4: RUN ML PIPELINE ===")
import tempfile
from vinu_features.compute.ml_models.runner import run_ml_step
from vinu_features.compute.ml_models.registry import list_models, train_and_predict, select_best, oos_ic

# Create temp directory for parquet
run_dir = Path(tempfile.mkdtemp(prefix='ml_test_'))
import pyarrow as pa
import pyarrow.parquet as pq
# Only keep columns needed: date (index), close, and features
table = pa.Table.from_pandas(features_df[['date', 'close'] + feature_cols])
pq.write_table(table, run_dir / 'features.parquet')
log('parquet_write', 0, 'PASS', f'saved to {run_dir / "features.parquet"}')

models_to_test = ['ridge', 'random_forest', 'xgboost', 'lightgbm', 'catboost']
results = {}
for model_name in models_to_test:
    t1 = time.time()
    try:
        result_path = run_ml_step(
            run_dir=run_dir,
            ml_model=model_name,
            ml_label='forward_return_1',
            feature_columns=feature_cols,
        )
        elapsed = time.time() - t1
        if result_path:
            with open(run_dir / 'oos_metrics.json') as f:
                metrics = json.load(f)
            log(f'ml_{model_name}', elapsed, 'PASS',
                f'OOS_IC={metrics["oos_ic"]:.4f}, train={metrics["train_count"]}, test={metrics["test_count"]}')
            results[model_name] = metrics
        else:
            log(f'ml_{model_name}', elapsed, 'WARN', 'Pipeline returned None')
    except Exception as e:
        log(f'ml_{model_name}', time.time()-t1, 'FAIL', str(e)[:200])

# ── Step 5: Test select_best() ──
print("\n=== STEP 5: AUTO MODEL SELECTION ===")
t1 = time.time()
try:
    # Build X/y manually for select_best
    from vinu_features.compute.ml_models.labels.labels import build_label_column
    rows = features_df.to_dict('records')
    y = build_label_column(rows, 'forward_return_1')
    X_rows, y_clean = [], []
    for i, row in enumerate(rows):
        if y[i] is not None:
            vals = [row.get(c) for c in feature_cols]
            if any(v is None for v in vals):
                continue
            X_rows.append(vals)
            y_clean.append(y[i])
    if len(X_rows) >= 10:
        split = int(len(X_rows) * 0.8)
        X_tr, X_te = X_rows[:split], X_rows[split:]
        y_tr, y_te = y_clean[:split], y_clean[split:]
        best_name, best_ic = select_best(X_tr, y_tr, X_te, y_te, candidates=['ridge', 'random_forest', 'xgboost'])
        log('select_best', time.time()-t1, 'PASS', f'best={best_name}, best_IC={best_ic:.4f}')
except Exception as e:
    log('select_best', time.time()-t1, 'FAIL', str(e)[:300])

# ── Step 6: CUDA-Accelerated XGBoost ──
print("\n=== STEP 6: CUDA XGBOOST TEST ===")
t1 = time.time()
try:
    import xgboost as xgb
    # Build X/y from the features dataframe
    X_arr = features_df[feature_cols].dropna().values.astype(np.float32)
    # Forward returns as target
    close_arr = features_df['close'].values.astype(np.float32)
    fwd_ret = (close_arr[1:] - close_arr[:-1]) / close_arr[:-1]
    X_arr = X_arr[:-1]  # align
    y_arr = fwd_ret
    log('cuda_data', 0, 'PASS', f'X={X_arr.shape}, y={y_arr.shape}')
    
    split = int(len(X_arr) * 0.8)
    X_tr, X_te = X_arr[:split], X_arr[split:]
    y_tr, y_te = y_arr[:split], y_arr[split:]

    # CPU baseline
    cpu_model = xgb.XGBRegressor(n_estimators=50, max_depth=5, verbosity=0)
    t_cpu = time.time()
    cpu_model.fit(X_tr, y_tr)
    cpu_preds = cpu_model.predict(X_te)
    cpu_time = time.time() - t_cpu
    from scipy.stats import spearmanr
    cpu_ic, _ = spearmanr(cpu_preds, y_te)

    # GPU with CUDA
    gpu_model = xgb.XGBRegressor(n_estimators=50, max_depth=5, verbosity=0,
                                  tree_method='hist', device='cuda')
    t_gpu = time.time()
    gpu_model.fit(X_tr, y_tr)
    gpu_preds = gpu_model.predict(X_te)
    gpu_time = time.time() - t_gpu
    gpu_ic, _ = spearmanr(gpu_preds, y_te)

    log('xgb_cpu', 0, 'PASS', f'OOS_IC={cpu_ic:.4f}, time={cpu_time:.2f}s')
    log('xgb_gpu', 0, 'PASS', f'OOS_IC={gpu_ic:.4f}, time={gpu_time:.2f}s, speedup={cpu_time/gpu_time:.1f}x')

    # LightGBM
    import lightgbm as lgb
    lgb_cpu = lgb.LGBMRegressor(n_estimators=50, max_depth=5, verbose=-1)
    t_lgb = time.time()
    lgb_cpu.fit(X_tr, y_tr)
    lgb_preds = lgb_cpu.predict(X_te)
    lgb_ic, _ = spearmanr(lgb_preds, y_te)
    log('lgb_cpu', time.time()-t_lgb, 'PASS', f'OOS_IC={lgb_ic:.4f}')
    
except Exception as e:
    log('cuda_test', 0, 'FAIL', str(e)[:300])
    import traceback
    log('cuda_traceback', 0, 'FAIL', traceback.format_exc()[:500])

# ── Summary ──
print("\n=== SUMMARY ===")
log('total', 0, 'DONE', f'Tested {len(models_to_test)} models, CUDA available: USE_CUDA={xgb.build_info().get("USE_CUDA", "?")}')
for name, m in results.items():
    log(f'summary_{name}', 0, 'INFO', f'OOS_IC={m["oos_ic"]:.4f}')
