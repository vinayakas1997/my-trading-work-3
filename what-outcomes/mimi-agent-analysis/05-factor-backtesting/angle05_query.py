"""Angle 05: Factor Backtesting — long/short portfolio from alpha factors."""
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

# ── Local backtest_factor (fixes min_assets=10 -> 2 for 4 tickers) ──
from vinu_tools.compute.factor_backtest import (
    _annualization_factor, _compute_metrics, FactorBacktestResult, WeightScheme
)

def backtest_factor_4t(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    weight_scheme: WeightScheme = "equal",
    long_quantile: float = 0.25,
    short_quantile: float = 0.25,
    top_n: int | None = None,
    freq: str = "1d",
    compute_turnover: bool = False,
    min_assets: int = 2,
) -> FactorBacktestResult:
    common_idx = factor_values.index.intersection(forward_returns.index)
    if len(common_idx) == 0:
        raise ValueError("No overlapping dates")
    fv = factor_values.loc[common_idx]
    fr = forward_returns.loc[common_idx]
    n_assets = fv.shape[1]
    positions_list: list[pd.Series] = []
    portfolio_returns_list: list[float] = []
    long_returns_list: list[float] = []
    short_returns_list: list[float] = []
    for t in common_idx:
        f_t = fv.loc[t]
        r_t = fr.loc[t]
        valid = f_t.notna() & r_t.notna()
        f_valid = f_t[valid]
        r_valid = r_t[valid]
        if len(f_valid) < min_assets:
            portfolio_returns_list.append(0.0)
            long_returns_list.append(0.0)
            short_returns_list.append(0.0)
            positions_list.append(pd.Series(0.0, index=fr.columns))
            continue
        ranks = f_valid.rank()
        n = len(ranks)
        if top_n is not None:
            long_mask = ranks >= (n - top_n + 1)
            short_mask = ranks <= top_n
        else:
            long_cut = int(n * (1 - long_quantile))
            short_cut = int(n * short_quantile)
            long_mask = ranks >= long_cut + 1 if long_cut < n else ranks > 0
            short_mask = ranks <= short_cut if long_cut > 0 else ranks < 0
        long_idx = ranks[long_mask].index
        short_idx = ranks[short_mask].index
        weight = pd.Series(0.0, index=ranks.index)
        if weight_scheme in ("equal", "top_quantile"):
            if len(long_idx) > 0:
                weight[long_idx] = 1.0 / len(long_idx)
            if weight_scheme != "top_quantile" and len(short_idx) > 0:
                weight[short_idx] = -1.0 / len(short_idx)
        elif weight_scheme == "rank":
            long_weights = ranks[long_idx] - ranks[long_idx].min() + 1
            weight[long_idx] = long_weights / long_weights.sum()
            if len(short_idx) > 0:
                short_weights = ranks[short_idx].max() + 1 - ranks[short_idx]
                weight[short_idx] = -short_weights / short_weights.sum()
        elif weight_scheme == "vol_parity":
            if len(long_idx) > 0:
                vol = r_valid[long_idx].std()
                w = (1.0 / vol) if vol > 0 else 0.0
                weight[long_idx] = w
                ws = weight[long_idx].sum()
                if ws > 0: weight[long_idx] /= ws
            if len(short_idx) > 0:
                vol = r_valid[short_idx].std()
                w = (1.0 / vol) if vol > 0 else 0.0
                weight[short_idx] = -w / abs(weight[short_idx]).sum() if abs(weight[short_idx]).sum() > 0 else 0.0
        pos = pd.Series(0.0, index=fr.columns)
        pos[weight.index] = weight
        positions_list.append(pos)
        period_return = float((pos * r_valid).sum())
        portfolio_returns_list.append(period_return)
        long_pos = pos.clip(lower=0)
        short_pos = -pos.clip(upper=0)
        long_returns_list.append(float((long_pos * r_valid).sum()))
        short_returns_list.append(float((short_pos * r_valid).sum()))
    portfolio_returns = pd.Series(portfolio_returns_list, index=common_idx, name="portfolio_returns")
    long_returns = pd.Series(long_returns_list, index=common_idx, name="long_returns")
    short_returns = pd.Series(short_returns_list, index=common_idx, name="short_returns")
    positions = pd.DataFrame(positions_list, index=common_idx)
    equity_curve = (1 + portfolio_returns).cumprod()
    running_max = equity_curve.cummax()
    drawdown_series = (equity_curve - running_max) / running_max
    metrics = _compute_metrics(portfolio_returns, freq)
    turnover_series = None
    if compute_turnover and len(positions) > 1:
        to = []
        for i in range(1, len(positions)):
            prev = positions.iloc[i - 1]
            curr = positions.iloc[i]
            changed = (prev.abs() > 0) | (curr.abs() > 0)
            to.append(float((prev[changed] - curr[changed]).abs().sum() / 2))
        turnover_series = pd.Series(to, index=positions.index[1:], name="turnover")
        metrics["mean_turnover"] = round(float(turnover_series.mean()), 4)
    return FactorBacktestResult(
        portfolio_returns, long_returns, short_returns, positions,
        metrics, equity_curve, drawdown_series, turnover_series
    )

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
        else:
            log(f'fetch_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
    except Exception as e:
        log(f'fetch_{sym}', time.time()-t1, 'FAIL', str(e))
log('fetch_all', time.time()-t0, 'DONE', f'{len(ohlcv)} tickers')

# ── Step 2: Build Panel ──
print("\n=== STEP 2: BUILD PANEL ===")
panel = {}
for col in ['open', 'high', 'low', 'close', 'volume']:
    frames = {sym: ohlcv[sym][col] for sym in TICKERS if col in ohlcv[sym].columns}
    panel[col] = pd.DataFrame(frames) if frames else pd.DataFrame()
panel['returns'] = panel['close'].pct_change()
log('panel_built', 0, 'PASS', f'close={panel["close"].shape}, returns={panel["returns"].shape}')

# ── Step 3: Compute Factors (skip VWAP-requiring ones) ──
print("\n=== STEP 3: COMPUTE FACTORS ===")
from vinu_tools.compute.factor_expressions import compute_expression

test_factors = [
    'alpha101_001', 'alpha101_010', 'alpha101_101',
    'gtja191_001', 'qlib158_ma5', 'qlib158_roc20',
    'academic_bab',
]
factor_values = {}
t0 = time.time()
for fid in test_factors:
    t1 = time.time()
    try:
        fv = compute_expression(fid, panel)
        factor_values[fid] = fv
        log(f'compute_{fid}', time.time()-t1, 'PASS',
            f'shape={fv.shape}, vals=[{fv.min().min():.4f}, {fv.max().max():.4f}]')
    except Exception as e:
        log(f'compute_{fid}', time.time()-t1, 'FAIL', str(e))
log('compute_all', time.time()-t0, 'DONE', f'{len(factor_values)} factors')

# ── Step 4: Backtest Each Factor ──
print("\n=== STEP 4: FACTOR BACKTESTING ===")
if panel.get('returns') is not None and factor_values:
    fwd_ret = panel['returns'].shift(-1)
    common_idx = fwd_ret.index.intersection(
        list(factor_values.values())[0].index) if factor_values else []
    if len(common_idx) > 1:
        fwd_ret = fwd_ret.loc[common_idx[:-1]]
        weight_schemes = ['equal', 'rank', 'vol_parity', 'top_quantile']

        for fid, fv in factor_values.items():
            print(f'\n--- {fid} ---')
            fv_aligned = fv.loc[common_idx[:-1]]
            for ws in weight_schemes:
                t1 = time.time()
                try:
                    res = backtest_factor_4t(fv_aligned, fwd_ret, weight_scheme=ws,
                                              long_quantile=0.25, short_quantile=0.25,
                                              freq='1d', compute_turnover=True,
                                              min_assets=2)
                    m = res.metrics
                    log(f'{fid}_{ws}', time.time()-t1, 'PASS',
                        f'SR={m["sharpe_ratio"]:.2f}, '
                        f'ret={m["total_return"]:.4f}, '
                        f'DD={m["max_drawdown"]:.4f}, '
                        f'WR={m["win_rate"]:.2f}, '
                        f'PF={m["profit_factor"]:.2f}, '
                        f'TO={m.get("mean_turnover", "?"):.3f}')
                except Exception as e:
                    log(f'{fid}_{ws}', time.time()-t1, 'FAIL', str(e))

        # ── Step 5: Cross-Family Comparison ──
        print('\n=== STEP 5: FACTOR COMPARISON ===')
        t1 = time.time()
        try:
            aligned = {fid: fv.loc[fwd_ret.index.intersection(fv.index)]
                       for fid, fv in factor_values.items()
                       if fid in factor_values}
            if len(aligned) >= 2:
                from vinu_tools.compute.factor_backtest import compare_factors
                # Patch compare_factors to use our backtest
                # Use direct computation instead
                comparison_data = []
                for name, fv_a in aligned.items():
                    try:
                        r = backtest_factor_4t(fv_a, fwd_ret, weight_scheme='rank',
                                                long_quantile=0.25, freq='1d',
                                                min_assets=2)
                        comparison_data.append({"factor": name, **r.metrics})
                    except Exception as e:
                        comparison_data.append({"factor": name, "error": str(e)})
                comp = pd.DataFrame(comparison_data).set_index("factor")
                log('compare_factors', time.time()-t1, 'PASS', comp.to_string())
            else:
                log('compare_factors', time.time()-t1, 'WARN', 'Too few factors')
        except Exception as e:
            log('compare_factors', time.time()-t1, 'FAIL', str(e))
    else:
        log('backtest', 0, 'FAIL', f'Not enough periods ({len(common_idx)})')
else:
    log('backtest', 0, 'FAIL', 'Missing data')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 05 factor backtesting finished')
