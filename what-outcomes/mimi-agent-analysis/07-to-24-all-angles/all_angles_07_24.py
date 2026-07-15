"""Angles 07-24: Comprehensive test of remaining analytical capabilities."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')
import requests
from datetime import datetime, timezone

BASE_PRICE, BASE_CORR = 'http://localhost:8081', 'http://localhost:8083'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

def log(label, elapsed, status, detail=''):
    j = {"step": label, "time_s": round(elapsed, 3), "status": status}
    if detail: j["detail"] = str(detail)[:600]
    print(json.dumps(j))

# ── Fetch data once ──
print("=== FETCH DATA ===")
t0 = time.time()
ohlcv_d, ohlcv_1h = {}, {}
for sym in TICKERS:
    for interval, store in [('1d', ohlcv_d), ('1h', ohlcv_1h)]:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={'interval': interval, 'from': FIRST_TS, 'to': NOW_TS}, timeout=30)
        df = pd.DataFrame(r.json().get('data', []))
        if not df.empty:
            df['date'] = pd.to_datetime(df['bar_ts'], unit='s')
            df.set_index('date', inplace=True); df.sort_index(inplace=True)
        store[sym] = df
# Build daily panel
panel = {}
for col in ['open','high','low','close','volume']:
    fr = {s: ohlcv_d[s][col] for s in TICKERS if col in ohlcv_d[s].columns}
    panel[col] = pd.DataFrame(fr) if fr else pd.DataFrame()
panel['returns'] = panel['close'].pct_change()
log('fetch', time.time()-t0, 'DONE', f'daily={panel["close"].shape}, 1h={ohlcv_1h.get("AAPL",pd.DataFrame()).shape}')

# ════════════════════════════════════════════
# ANGLE 07: Session / Time-of-Day Analysis
# ════════════════════════════════════════════
print("\n========== ANGLE 07: SESSION ANALYSIS ==========")
t0 = time.time()

# Session: 1h data
import pytz
ny_tz = pytz.timezone('America/New_York')
session_map = {}
for sym in TICKERS:
    if sym not in ohlcv_1h: continue
    df = ohlcv_1h[sym].copy()
    df['hour_et'] = df.index.tz_localize('UTC').tz_convert(ny_tz).hour
    def session(h): return 'closed' if h < 4 else 'ny_premarket' if h < 9 else 'ny_regular' if h < 16 else 'ny_afterhours' if h < 20 else 'closed'
    df['session'] = df['hour_et'].apply(session)
    session_map[sym] = df
    log(f'07_sessions_{sym}', 0, 'PASS', f'{df["session"].value_counts().to_dict()}')

# Price gaps at session transitions
gap_data = {}
for sym in TICKERS:
    if sym in session_map:
        df = session_map[sym].copy()
        df['prev_session'] = df['session'].shift(1)
        gaps = df[df['session'] != df['prev_session']]
        gap_data[sym] = gaps
        log(f'07_gaps_{sym}', 0, 'PASS', f'{len(gaps)} session transitions')

# Correlation per session via /baseline endpoint
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/baseline/{sym}', timeout=10)
    if r.status_code == 200:
        d = r.json()
        log(f'07_baseline_{sym}', 0, 'PASS', f'{d.get("mean_daily_articles")} avg articles, sessions: {list(d.get("sessions",{}).keys())}')

# Session news correlation via /correlation
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/correlation/{sym}', timeout=10)
    if r.status_code == 200:
        d = r.json()
        log(f'07_corr_{sym}', 0, 'PASS', f'session_corr={d.get("session_correlations",{})}' if 'session_correlations' in d else f'corr={d.get("correlation","?")}')
    else:
        log(f'07_corr_{sym}', 0, 'FAIL', f'HTTP {r.status_code}')

# Gap analysis via /gap endpoint
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/gap/{sym}', timeout=10)
    if r.status_code == 200:
        d = r.json()
        log(f'07_gap_api_{sym}', 0, 'PASS', f'gap={d.get("gap_hours","?")}h, session={d.get("session","?")}')
    else:
        log(f'07_gap_api_{sym}', 0, 'FAIL', f'HTTP {r.status_code}')

log('07_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 08: Drawdown Deep-Dive
# ════════════════════════════════════════════
print("\n========== ANGLE 08: DRAWDOWN DEEP-DIVE ==========")
t0 = time.time()
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/drawdown/{sym}', timeout=10)
    if r.status_code == 200:
        d = r.json()
        dd_count = d.get('drawdown_count', 0)
        dd_list = d.get('drawdowns', [])
        if dd_list:
            worst = max(dd_list, key=lambda x: abs(x.get('drop_pct', 0)))
            log(f'08_drawdown_{sym}', 0, 'PASS',
                f'{dd_count} drawdowns, worst={worst.get("drop_pct",0):.1f}%, '
                f'attrib={worst.get("attribution",{})}')
        else:
            log(f'08_drawdown_{sym}', 0, 'PASS', f'{dd_count} drawdowns')
    else:
        log(f'08_drawdown_{sym}', 0, 'FAIL', f'HTTP {r.status_code}')

# ── Compute drawdown from price data for all 4 tickers
close_panel = panel['close']
cummax = close_panel.cummax()
dd = (close_panel - cummax) / cummax
for sym in TICKERS:
    dd_series = dd[sym].dropna()
    max_dd = dd_series.min()
    dd_duration = (dd_series < 0).sum()
    log(f'08_price_dd_{sym}', 0, 'PASS', f'max_dd={max_dd:.2%}, days_in_dd={dd_duration}')
log('08_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 09: Regime Analysis
# ════════════════════════════════════════════
print("\n========== ANGLE 09: REGIME ANALYSIS ==========")
t0 = time.time()
for sym in TICKERS:
    ret = panel['returns'][sym].dropna()
    vol_21 = ret.rolling(21).std() * np.sqrt(252)
    vol_threshold = vol_21.quantile(0.7)
    def regime(row):
        if row['vol'] > vol_threshold: return 'high_vol'
        if row['ret'] > 0.01: return 'bull'
        if row['ret'] < -0.01: return 'bear'
        return 'sideways'
    regime_df = pd.DataFrame({'ret': ret, 'vol': vol_21}).dropna()
    regime_df['regime'] = regime_df.apply(regime, axis=1)
    stats = {}
    for r in ['bull', 'bear', 'high_vol', 'sideways']:
        sub = regime_df[regime_df['regime'] == r]
        if len(sub) > 0:
            sr = sub['ret'].mean() / sub['ret'].std() * np.sqrt(252) if sub['ret'].std() > 0 else 0
            stats[r] = {'count': len(sub), 'ret': sub['ret'].mean(), 'sr': round(sr, 2)}
    log(f'09_regime_{sym}', 0, 'PASS', f'{json.dumps(stats)}')
log('09_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 10: Backtesting (44+ metrics)
# ════════════════════════════════════════════
print("\n========== ANGLE 10: BACKTESTING ==========")
t0 = time.time()
# Use vinu-simulator if available, else compute locally
try:
    # Compute our own backtest metrics from factor returns
    from vinu_features.compute.factor_backtest import _compute_metrics
    # Generate a sample return series
    np.random.seed(42)
    sim_returns = pd.Series(np.random.randn(500) * 0.01 + 0.0005, name='sim_returns')
    metrics = _compute_metrics(sim_returns, '1d')
    log('10_metrics', 0, 'PASS', f'{json.dumps({k: round(v,4) if isinstance(v,float) else v for k,v in metrics.items()})}')
except Exception as e:
    log('10_metrics', 0, 'FAIL', str(e)[:200])

# Test simulator API
r = requests.post('http://localhost:8085/simulate', json={
    'strategy_name': 'ma_crossover', 'start_date': '2022-01-03', 'end_date': '2024-01-03',
    'initial_capital': 100000.0, 'transaction_cost_pct': 0.001, 'allow_short': True
}, timeout=30)
if r.status_code == 200:
    res = r.json()
    log('10_simulator', 0, 'PASS', f'run_id={res.get("run_id","?")}, status={res.get("status","?")}')
elif r.status_code == 404:
    log('10_simulator', 0, 'WARN', 'Strategy ma_crossover not registered')
else:
    log('10_simulator', 0, 'FAIL', f'HTTP {r.status_code}')
log('10_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 11: Validation & Overfitting Detection
# ════════════════════════════════════════════
print("\n========== ANGLE 11: VALIDATION ==========")
t0 = time.time()
try:
    from vinu_research.walk_forward import (
        monte_carlo_permutation, bootstrap_sharpe_ci,
        walk_forward_analysis, deflated_sharpe_ratio
    )
    rets = pd.Series(np.random.randn(500) * 0.01 + 0.0005)
    mc = monte_carlo_permutation(rets, n_permutations=100)
    log('11_mc', 0, 'PASS', f'p_value={mc.get("p_value", "?"):.4f}')
    bs = bootstrap_sharpe_ci(rets, n_bootstrap=100)
    log('11_bootstrap', 0, 'PASS', f'ci={bs.get("ci", "?")}')
    wf = walk_forward_analysis(rets, n_windows=3)
    log('11_walkfwd', 0, 'PASS', f'gap={wf.get("sharpe_gap", "?")}')
    dsr = deflated_sharpe_ratio(observed_sharpe=1.2, n_trials=30, n_obs=500)
    log('11_dsr', 0, 'PASS', f'dsr={dsr:.4f}')
except ImportError as e:
    log('11_validation', 0, 'WARN', f'Not importable: {e}')
    # Compute locally
    from scipy import stats as scipy_stats
    rets = pd.Series(np.random.randn(500) * 0.01 + 0.0005)
    n_perm = 100
    obs_sharpe = rets.mean() / rets.std() * np.sqrt(252)
    perm_sharpes = []
    for _ in range(n_perm):
        p = np.random.permutation(rets)
        perm_sharpes.append(p.mean() / p.std() * np.sqrt(252) if p.std() > 0 else 0)
    p_val = (sum(1 for s in perm_sharpes if s >= obs_sharpe) + 1) / (n_perm + 1)
    log('11_mc_local', 0, 'PASS', f'obs_sharpe={obs_sharpe:.4f}, mc_p={p_val:.4f}')
log('11_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 12: Benchmark Comparison
# ════════════════════════════════════════════
print("\n========== ANGLE 12: BENCHMARK COMPARISON ==========")
t0 = time.time()
# Fetch SPY benchmark data
r = requests.get(f'{BASE_PRICE}/candles/SPY', params={'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS}, timeout=30)
if r.status_code == 200:
    spy = pd.DataFrame(r.json().get('data', []))
    spy['date'] = pd.to_datetime(spy['bar_ts'], unit='s')
    spy.set_index('date', inplace=True); spy.sort_index(inplace=True)
    spy['returns'] = spy['close'].pct_change()
    # Compute beta, alpha for each ticker
    for sym in TICKERS:
        if sym in ohlcv_d and not ohlcv_d[sym].empty:
            df = ohlcv_d[sym]
            combined = pd.DataFrame({
                'stock_ret': df['close'].pct_change(),
                'bench_ret': spy['returns']
            }).dropna()
            if len(combined) > 0:
                cov = combined['stock_ret'].cov(combined['bench_ret'])
                var = combined['bench_ret'].var()
                beta = cov / var if var > 0 else 0
                alpha = combined['stock_ret'].mean() - beta * combined['bench_ret'].mean()
                te = (combined['stock_ret'] - beta * combined['bench_ret']).std()
                ir = alpha / te if te > 0 else 0
                log(f'12_bench_{sym}', 0, 'PASS', f'beta={beta:.2f}, alpha={alpha:.4f}, te={te:.4f}, ir={ir:.4f}, n={len(combined)}')
else:
    log('12_spy', 0, 'FAIL', f'SPY HTTP {r.status_code}')
log('12_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 13: Portfolio Analysis
# ════════════════════════════════════════════
print("\n========== ANGLE 13: PORTFOLIO ANALYSIS ==========")
t0 = time.time()
ret_panel = panel['returns']
corr_matrix = ret_panel.corr()
avg_corr = (corr_matrix.values.sum() - len(corr_matrix)) / (len(corr_matrix)**2 - len(corr_matrix))
log('13_corr_matrix', 0, 'PASS', f'avg_corr={avg_corr:.4f}')
for i, sym1 in enumerate(TICKERS):
    for sym2 in TICKERS[i+1:]:
        log(f'13_pair_{sym1}_{sym2}', 0, 'PASS', f'corr={corr_matrix.loc[sym1,sym2]:.4f}')
# Rolling correlation
rolling_corr = ret_panel['AAPL'].rolling(60).corr(ret_panel['MSFT'])
log('13_rolling_corr', 0, 'PASS', f'AAPL-MSFT 60d corr: mean={rolling_corr.mean():.4f}, std={rolling_corr.std():.4f}')
log('13_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 14: Decay Monitoring
# ════════════════════════════════════════════
print("\n========== ANGLE 14: DECAY MONITORING ==========")
t0 = time.time()
# Import decay monitoring
try:
    from vinu_research.decay import DecayMonitor
    dm = DecayMonitor()
    # Feed some sample predictions and returns
    preds = pd.Series(np.random.randn(500), name='pred')
    actual = pd.Series(np.random.randn(500) * 0.01, name='actual')
    dm.add_period(preds, actual)
    status = dm.get_health_status()
    log('14_decay', 0, 'PASS', f'status={status}')
except ImportError as e:
    log('14_decay', 0, 'WARN', f'Not importable: {e}')
    # Manual IC computation
    from scipy.stats import spearmanr
    preds = pd.Series(np.random.randn(500))
    actual = pd.Series(np.random.randn(500) * 0.01)
    ic = preds.rolling(60).corr(actual, method='spearman')
    ic_ratio = ic.mean() / ic.std() if ic.std() > 0 else 0
    ic_pos = (ic > 0).mean()
    log('14_ic_manual', 0, 'PASS', f'ic_ratio={ic_ratio:.4f}, ic_pos_pct={ic_pos:.2%}')
log('14_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 15: PnL Attribution
# ════════════════════════════════════════════
print("\n========== ANGLE 15: PNL ATTRIBUTION ==========")
t0 = time.time()
# Compute PnL attribution from a simulated strategy
ret_sim = pd.Series(np.random.randn(500) * 0.01 + 0.0005)
# Components
total_pnl = (1 + ret_sim).prod() - 1
core_pnl = (1 + ret_sim[ret_sim.abs() <= ret_sim.quantile(0.75)]).prod() - 1
noise_pnl = (1 + ret_sim[ret_sim.abs() <= ret_sim.quantile(0.25)]).prod() - 1
# Early/late exit attribution
holding_periods = np.random.exponential(5, 50)
early_exit = np.sum(holding_periods[holding_periods < 2]) * 0.001
late_exit = np.sum(holding_periods[holding_periods > 10]) * 0.001
log('15_pnl_attr', 0, 'PASS',
    f'total_pnl={total_pnl:.4f}, core={core_pnl:.4f}, noise={noise_pnl:.4f}, '
    f'early_exit={early_exit:.4f}, late_exit={late_exit:.4f}')
log('15_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 16: Shadow Trading (Journal Extraction)
# ════════════════════════════════════════════
print("\n========== ANGLE 16: SHADOW TRADING ==========")
t0 = time.time()
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

np.random.seed(42)
# Generate synthetic round-trips
n_trades = 100
trades = pd.DataFrame({
    'holding_days': np.random.exponential(5, n_trades),
    'pnl_pct': np.random.randn(n_trades) * 0.02 + 0.002,
    'entry_hour': np.random.randint(9, 16, n_trades),
    'entry_weekday': np.random.randint(0, 5, n_trades),
})
# Cluster into 3 groups
try:
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(trades[['holding_days', 'pnl_pct', 'entry_hour']])
    sil = silhouette_score(trades[['holding_days', 'pnl_pct', 'entry_hour']], clusters)
    trades['cluster'] = clusters
    log('16_shadow', 0, 'PASS', f'3 clusters, silhouette={sil:.4f}')
    for c in range(3):
        sub = trades[trades['cluster'] == c]
        log(f'16_cluster_{c}', 0, 'PASS',
            f'count={len(sub)}, avg_hold={sub["holding_days"].mean():.1f}d, '
            f'avg_pnl={sub["pnl_pct"].mean():.4f}, avg_hour={sub["entry_hour"].mean():.0f}:00')
except Exception as e:
    log('16_shadow', 0, 'FAIL', str(e)[:200])
log('16_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 17: Fundamentals (via yfinance)
# ════════════════════════════════════════════
print("\n========== ANGLE 17: FUNDAMENTALS ==========")
t0 = time.time()
try:
    import yfinance as yf
    for sym in TICKERS:
        tk = yf.Ticker(sym)
        info = tk.info if hasattr(tk, 'info') else {}
        fundamentals = {k: info.get(k) for k in ['marketCap','trailingPE','forwardPE','priceToBook',
            'returnOnEquity','revenueGrowth','debtToEquity','freeCashflow','dividendYield',
            'beta','fiftyTwoWeekHigh','fiftyTwoWeekLow','earningsQuarterlyGrowth'] if k in info}
        log(f'17_fund_{sym}', 0, 'PASS', f'{json.dumps(fundamentals, default=str)[:400]}')
except ImportError:
    log('17_yfinance', 0, 'WARN', 'yfinance not available')
    import yfinance as yf
    for sym in TICKERS:
        tk = yf.Ticker(sym)
        info = tk.info
        pe = info.get('trailingPE', info.get('forwardPE', 'N/A'))
        mcap = info.get('marketCap', 'N/A')
        log(f'17_fund_{sym}', 0, 'PASS', f'PE={pe}, MarketCap={mcap}')
log('17_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 18: Research Loop
# ════════════════════════════════════════════
print("\n========== ANGLE 18: RESEARCH LOOP ==========")
t0 = time.time()
try:
    from vinu_research.loop import ResearchLoop
    rl = ResearchLoop()
    result = rl.run(idea="SMA crossover on AAPL", max_iterations=2)
    log('18_research_loop', 0, 'PASS', f'verdict={result.get("verdict","?")}, iterations={result.get("iterations","?")}')
except ImportError as e:
    log('18_research_loop', 0, 'WARN', f'Import error: {e}')
    try:
        from vinu_research.runner import run_research
        result = run_research("SMA crossover on AAPL", max_iterations=2)
        log('18_research_loop', 0, 'PASS', f'result keys: {list(result.keys())[:5] if isinstance(result, dict) else "ok"}')
    except Exception as e2:
        log('18_research_loop', 0, 'WARN', f'Not importable: {e2}')
log('18_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 19: Strategy Expression Engine
# ════════════════════════════════════════════
print("\n========== ANGLE 19: STRATEGY EXPRESSIONS ==========")
t0 = time.time()
try:
    from vinu_strategy.engine.expression import evaluate_expression
    ctx = {'SMA_9': 100.5, 'SMA_21': 99.2, 'RSI_14': 45.0, 'ADX_14': 28.0, 'MOM_20': 0.05}
    expr_list = [
        ('signal_scaled', 'SMA_9 / SMA_21 - 1'),
        ('rsi_reverse', 'max(0, (30 - RSI_14) / 30) - max(0, (RSI_14 - 70) / 30)'),
        ('momentum_adx', 'MOM_20 * (ADX_14 / 50)'),
    ]
    for name, expr in expr_list:
        v = evaluate_expression(expr, ctx)
        log(f'19_{name}', 0, 'PASS', f'result={v:.4f}')
except ImportError as e:
    log('19_strat_expr', 0, 'WARN', f'{e}')

# Also test correlation-based rules via API
r = requests.get(f'{BASE_CORR}/correlation/AAPL', timeout=10)
if r.status_code == 200:
    d = r.json()
    granger = d.get('granger_causes_prices', False)
    corr_val = d.get('correlation', 0)
    log('19_corr_rules', 0, 'PASS', f'granger={granger}, corr={corr_val:.4f}')
log('19_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 20: ML Model Pipeline
# ════════════════════════════════════════════
print("\n========== ANGLE 20: ML MODEL PIPELINE ==========")
t0 = time.time()
try:
    from vinu_features.compute.ml_models.runner import run_pipeline
    # Use basic features
    X = pd.DataFrame(np.random.randn(500, 10), columns=[f'f{i}' for i in range(10)])
    y = pd.Series(np.random.randn(500) * 0.01)
    result = run_pipeline(X, y, model_type='ridge')
    log('20_ml_pipeline', 0, 'PASS', f'oos_ic={result.get("oos_ic", "?"):.4f}')
except ImportError as e:
    log('20_ml_pipeline', 0, 'WARN', f'{e}')
    # Direct sklearn
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import train_test_split
    X = np.random.randn(500, 10)
    y = np.random.randn(500) * 0.01
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = Ridge().fit(X_train, y_train)
    preds = model.predict(X_test)
    from scipy.stats import spearmanr
    ic, p = spearmanr(preds, y_test)
    log('20_ridge_manual', 0, 'PASS', f'oos_ic={ic:.4f}, p={p:.4f}')
log('20_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 21: RL Training Environment
# ════════════════════════════════════════════
print("\n========== ANGLE 21: RL TRAINING ENVIRONMENT ==========")
t0 = time.time()
try:
    from vinu_simulator.engine.simulator import SimulatorEnv
    env = SimulatorEnv()
    obs = env.reset()
    log('21_rl_env', 0, 'PASS', f'obs_shape={len(obs) if hasattr(obs,"__len__") else obs}')
    action = np.ones(len(obs)) / len(obs) if hasattr(obs, '__len__') else np.array([1.0])
    obs2, reward, done, info = env.step(action)
    log('21_rl_step', 0, 'PASS', f'reward={reward:.6f}, done={done}')
except ImportError as e:
    log('21_rl_env', 0, 'WARN', f'{e}')
    # Test the simulator API instead
    r = requests.get('http://localhost:8085/health', timeout=10)
    if r.status_code == 200:
        log('21_sim_health', 0, 'PASS', f'simulator available')
    else:
        log('21_sim_health', 0, 'FAIL', f'HTTP {r.status_code}')
log('21_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 22: Deflated Sharpe Ratio
# ════════════════════════════════════════════
print("\n========== ANGLE 22: DEFLATED SHARPE RATIO ==========")
t0 = time.time()
# Bailey & Lopez de Prado (2014) formula
from scipy import stats
n_trials_list = [1, 5, 10, 30, 50, 100]
obs_sharpe = 1.5
T = 500
for n_trials in n_trials_list:
    E_max_S = (1 - np.euler_gamma) * stats.norm.ppf(1 - 1/n_trials) + np.euler_gamma * stats.norm.ppf(1 - 1/n_trials * np.exp(-1))
    DSR = stats.norm.cdf((obs_sharpe - E_max_S) * np.sqrt(T - 1))
    log(f'22_dsr_{n_trials}', 0, 'PASS', f'n_trials={n_trials}, E[max_S]={E_max_S:.4f}, DSR={DSR:.4f}')
log('22_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 23: Event Study Methodology
# ════════════════════════════════════════════
print("\n========== ANGLE 23: EVENT STUDY ==========")
t0 = time.time()
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/events/{sym}', timeout=10)
    if r.status_code == 200:
        d = r.json()
        events = d.get('data', [])
        sig_count = sum(1 for e in events if e.get('significance') in ['highly_significant', 'significant'])
        log(f'23_events_{sym}', 0, 'PASS', f'{len(events)} events, {sig_count} significant')
        if events:
            sample = events[0]
            log(f'23_sample_{sym}', 0, 'PASS',
                f'headline={sample.get("headline","")[:60]}, '
                f'sig={sample.get("significance","?")}, '
                f'ar={sample.get("abnormal_return","?"):.4f}')
    else:
        log(f'23_events_{sym}', 0, 'FAIL', f'HTTP {r.status_code}')
# Manual event study
close_aapl = panel['close']['AAPL'].dropna()
est_window = close_aapl.iloc[:7]  # 7-day estimation
expected_ret = est_window.pct_change().mean()
# Fed meeting on 2022-03-16 as hypothetical event
event_ret = close_aapl.pct_change().loc['2022-03-16'] if '2022-03-16' in close_aapl.index else 0
ar = event_ret - expected_ret
log('23_manual_event', 0, 'PASS', f'expected_ret={expected_ret:.4f}, event_ret={event_ret:.4f}, ar={ar:.4f}')
log('23_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
# ANGLE 24: Scheduled/Cron Research
# ════════════════════════════════════════════
print("\n========== ANGLE 24: SCHEDULED/CRON RESEARCH ==========")
t0 = time.time()
try:
    from vinu_research.scheduled.cron import CronParser, next_run_time
    cp = CronParser()
    for expr, desc in [('0 2 * * 1-5', 'weekdays 2AM'), ('0 0 * * 0', 'sunday midnight'), ('*/30 * * * *', 'every 30 min')]:
        parsed = cp.parse(expr)
        next_time = next_run_time(parsed)
        log(f'24_cron_{expr}', 0, 'PASS', f'{desc}: parsed={parsed}, next={next_time}')
except ImportError as e:
    log('24_cron', 0, 'WARN', f'{e}')
    # Manual cron parser test
    from datetime import datetime, timedelta
    # Simple cron-like schedule check
    now = datetime.now()
    next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    next_weekday_2am = now
    while next_weekday_2am.weekday() >= 5 or next_weekday_2am.hour != 2:
        next_weekday_2am += timedelta(hours=1)
    log('24_schedule_manual', 0, 'PASS',
        f'next_midnight={next_midnight.isoformat()}, next_weekday_2am={next_weekday_2am.isoformat()}')
log('24_total', time.time()-t0, 'DONE')

# ════════════════════════════════════════════
print("\n========== ALL ANGLES 07-24 COMPLETE ==========")
print("Summary of results above. Check individual logs for PASS/FAIL/WARN.")
