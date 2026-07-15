"""Angle 06: Expression DSL — custom alpha signals combining factors and operators."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    j = {"step": label, "time_s": round(elapsed, 3), "status": status}
    if detail: j["detail"] = str(detail)[:500]
    print(json.dumps(j))

# ── Local backtest (min_assets=2 for 4 tickers) ──
from vinu_features.compute.factor_backtest import _compute_metrics, FactorBacktestResult

def bt_factor(fv, fr, ws='rank', min_assets=2):
    common = fv.index.intersection(fr.index)
    if len(common) == 0: return None
    fv2, fr2 = fv.loc[common], fr.loc[common]
    pr, lr, sr, pl = [], [], [], []
    for t in common:
        ft, rt = fv2.loc[t], fr2.loc[t]
        valid = ft.notna() & rt.notna()
        fv_, rv_ = ft[valid], rt[valid]
        if len(fv_) < min_assets:
            pr.append(0.0); lr.append(0.0); sr.append(0.0)
            pl.append(pd.Series(0.0, index=fr.columns))
            continue
        r = fv_.rank(); n = len(r)
        lc = int(n * 0.75)
        sc = int(n * 0.25)
        lm = r >= (lc + 1 if lc < n else 0)
        sm = r <= sc if lc > 0 else r < 0
        li, si = r[lm].index, r[sm].index
        w = pd.Series(0.0, index=r.index)
        if ws == 'rank':
            lw = r[li] - r[li].min() + 1
            w[li] = lw / lw.sum()
            if len(si) > 0:
                sw = r[si].max() + 1 - r[si]
                w[si] = -sw / sw.sum()
        else:
            if len(li) > 0: w[li] = 1.0 / len(li)
            if ws != 'top_quantile' and len(si) > 0: w[si] = -1.0 / len(si)
        pos = pd.Series(0.0, index=fr.columns)
        pos[w.index] = w
        pl.append(pos)
        pr.append(float((pos * rv_).sum()))
        lp = pos.clip(lower=0)
        sp = -pos.clip(upper=0)
        lr.append(float((lp * rv_).sum()))
        sr.append(float((sp * rv_).sum()))
    prs = pd.Series(pr, index=common, name='pr')
    pos_df = pd.DataFrame(pl, index=common)
    eq = (1 + prs).cumprod()
    dd = (eq - eq.cummax()) / eq.cummax()
    m = _compute_metrics(prs, '1d')
    return FactorBacktestResult(prs, pd.Series(lr, index=common), pd.Series(sr, index=common), pos_df, m, eq, dd)

# ── Fetch Data ──
print("=== FETCH DATA ===")
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

panel = {}
for col in ['open','high','low','close','volume']:
    frames = {s: ohlcv[s][col] for s in TICKERS if col in ohlcv[s].columns}
    panel[col] = pd.DataFrame(frames) if frames else pd.DataFrame()
panel['returns'] = panel['close'].pct_change()
log('fetch', time.time()-t0, 'DONE', f'{panel["close"].shape}')

fwd_ret = panel['returns'].shift(-1)

# ── Section 1: compute_expression() — 11 Functions ──
print("\n=== 1: compute_expression() 11 Functions ===")
from vinu_features.compute.factor_expressions import compute_expression, list_expression_variables

# 1a: Simple ref
v = compute_expression('alpha101_001', panel)
log('simple_ref', 0, 'PASS', f'range=[{v.min().min():.4f},{v.max().max():.4f}]')

# 1b: 5 arithmetic combinations
for name, e in [('a+b','alpha101_001+alpha101_010'),('a-b','alpha101_001-alpha101_010'),
                 ('a*b','alpha101_001*alpha101_010'),('a/b','alpha101_001/alpha101_010'),
                 ('paren','(alpha101_001+alpha101_010)/2')]:
    v = compute_expression(e, panel)
    log(f'arith_{name}', 0, 'PASS', f'range=[{v.min().min():.4f},{v.max().max():.4f}]')

# 1c: All 11 functions
for name, e in [('rank','rank(alpha101_001)'),('zscore','zscore(alpha101_001)'),
                 ('ts_mean','ts_mean(alpha101_001,10)'),('ts_std','ts_std(alpha101_001,10)'),
                 ('ts_sum','ts_sum(alpha101_001,10)'),('ts_max','ts_max(alpha101_001,10)'),
                 ('ts_min','ts_min(alpha101_001,10)'),('abs','abs(alpha101_001)'),
                 ('neg','neg(alpha101_001)'),('sign','sign(alpha101_001)'),
                 ('delay','delay(alpha101_001,5)')]:
    v = compute_expression(e, panel)
    log(f'func_{name}', 0, 'PASS', f'range=[{v.min().min():.4f},{v.max().max():.4f}]')

# 1d: No-parens, nested, unary, combined
v = compute_expression('rank alpha101_001', panel)
log('no_parens', 0, 'PASS', '')
v = compute_expression('ts_mean(rank(alpha101_001), 10)', panel)
log('nested', 0, 'PASS', '')
v = compute_expression('-alpha101_001', panel)
log('unary_neg', 0, 'PASS', '')
v = compute_expression('rank(alpha101_001)*zscore(alpha101_010)+ts_mean(qlib158_ma5,5)', panel)
log('combined', 0, 'PASS', f'range=[{v.min().min():.4f},{v.max().max():.4f}]')

# 1e: list_expression_variables
vars_found = list_expression_variables('rank(alpha101_001)*zscore(gtja191_005)+alpha101_010')
log('list_vars', 0, 'PASS', f'{vars_found}')

# 1f: Error handling
try:
    compute_expression('unknown_factor_xyz', panel)
    log('err_unknown_factor', 0, 'FAIL', 'Should have raised')
except Exception as e: log('err_unknown_factor', 0, 'PASS', str(e)[:80])
try:
    compute_expression('bogus_fn(alpha101_001)', panel)
    log('err_unknown_func', 0, 'FAIL', 'Should have raised')
except Exception as e: log('err_unknown_func', 0, 'PASS', str(e)[:80])

# ── Section 2: QLib Evaluator ──
print("\n=== 2: QLib Evaluator ===")
try:
    from vinu_features.compute.bigger_recipe._alpha_expr.evaluator import evaluate_expression as qlib_eval
    arr = {c: panel[c].values for c in ['open','high','low','close','volume']}

    for name, e in [('close','$close'),('close-open','$close-$open'),
                     ('hl_spread','($high-$low)/$open'),
                     ('return','Ref($close,1)/$close-1'),
                     ('rank','Rank($close,20)')]:
        v = qlib_eval(e, arr)
        log(f'qlib_{name}', 0, 'PASS', f'shape={np.array(v).shape}')

    for fn in ['Corr($close,$volume,10)','$close>$open&&$volume>1000000',
               'Slope($close,20)','Rsquare($close,20)','IdxMax($close,20)','Resi($close,20)',
               'Quantile($close,20,0.5)','Greater($close,$open)']:
        v = qlib_eval(fn, arr)
        log(f'qlib_{fn[:15]}', 0, 'PASS', f'shape={np.array(v).shape}')
except ImportError as e:
    log('qlib', 0, 'WARN', f'Not importable: {e}')

# ── Section 3: Strategy Expression Engine ──
print("\n=== 3: Strategy Expression Engine ===")
try:
    from vinu_strategy.rules.expression import evaluate_expression as strat_eval
    ctx = {'SMA_9':100.5,'SMA_21':99.2,'RSI_14':45.0,'ADX_14':28.0}
    for name, e in [('simple','SMA_9/SMA_21-1'),('maxmin','max(RSI_14,ADX_14)/min(RSI_14,ADX_14)'),
                     ('abs','abs(SMA_9-SMA_21)'),('mod','SMA_9%10'),('power','ADX_14**2'),
                     ('ci','sma_9/sma_21-1')]:
        v = strat_eval(e, ctx)
        log(f'strat_{name}', 0, 'PASS', f'result={v}')
    for name, e in [('unknown','unknown_var+1'),('empty',''),
                     ('disallowed','import os')]:
        try:
            strat_eval(e, ctx)
            log(f'strat_err_{name}', 0, 'FAIL', 'Should have raised')
        except Exception as ex: log(f'strat_err_{name}', 0, 'PASS', str(ex)[:80])
except ImportError as e:
    log('strat', 0, 'WARN', f'Not importable: {e}')

# ── Section 4: Backtest Combined Expressions ──
print("\n=== 4: Backtest Combined Expressions ===")
combined = {
    'rank001_zscore010': 'rank(alpha101_001)*zscore(alpha101_010)',
    'rank001_plus_rank010': 'rank(alpha101_001)+rank(alpha101_010)',
    'ts_ma5_qlib158': 'ts_mean(qlib158_ma5,5)',
    'mom_rev_combo': 'rank(alpha101_001)*zscore(alpha101_101)',
    'three_factor': 'rank(alpha101_001)+zscore(alpha101_010)+sign(qlib158_ma5)',
}
results = {}
for name, e in combined.items():
    v = compute_expression(e, panel)
    results[name] = v
    log(f'compute_{name}', 0, 'PASS', f'range=[{v.min().min():.4f},{v.max().max():.4f}]')

common_idx = fwd_ret.index.intersection(list(results.values())[0].index)
if len(common_idx) > 1:
    fwd_ret2 = fwd_ret.loc[common_idx[:-1]]
    for name, fv in results.items():
        fv_a = fv.loc[common_idx[:-1]]
        bt = bt_factor(fv_a, fwd_ret2, 'rank')
        if bt:
            m = bt.metrics
            log(f'bt_{name}', 0, 'PASS',
                f'SR={m["sharpe_ratio"]:.2f}, ret={m["total_return"]:.4f}, DD={m["max_drawdown"]:.4f}')
else:
    log('combined_bt', 0, 'FAIL', 'Not enough periods')

print('\n=== DONE ===')
log('total', 0, 'DONE', 'Angle 06 Expression DSL finished')
