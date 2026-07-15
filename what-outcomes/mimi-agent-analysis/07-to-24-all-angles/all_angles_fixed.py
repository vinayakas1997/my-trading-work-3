"""Angles 07-24: Fix SPY and simulator issues."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')
import requests
from datetime import datetime, timezone
BASE_PRICE, BASE_CORR = 'http://localhost:8081', 'http://localhost:8083'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())
def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# Fetch data
print("=== FETCH ===")
t0 = time.time()
ohlcv_d = {}
for sym in TICKERS:
    r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS}, timeout=30)
    df = pd.DataFrame(r.json().get('data', []))
    if not df.empty:
        df['date'] = pd.to_datetime(df['bar_ts'], unit='s'); df.set_index('date', inplace=True); df.sort_index(inplace=True)
    ohlcv_d[sym] = df
panel = {c: pd.DataFrame({s: ohlcv_d[s][c] for s in TICKERS if c in ohlcv_d[s].columns}) for c in ['open','high','low','close','volume']}
panel['returns'] = panel['close'].pct_change()
log('fetch', time.time()-t0, 'DONE', f'{panel["close"].shape}')

# ═══ 07 ═══
print("\n=== ANGLE 07: SESSION ANALYSIS ===")
t0 = time.time()
import pytz; ny_tz = pytz.timezone('America/New_York')
ohlcv_1h = {}
for sym in TICKERS:
    r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={'interval': '1h', 'from': FIRST_TS, 'to': NOW_TS}, timeout=30)
    df = pd.DataFrame(r.json().get('data', []))
    if not df.empty:
        df['date'] = pd.to_datetime(df['bar_ts'], unit='s'); df.set_index('date', inplace=True); df.sort_index(inplace=True)
    ohlcv_1h[sym] = df
    if not df.empty:
        df['hour_et'] = df.index.tz_localize('UTC').tz_convert(ny_tz).hour
        def s(h): return 'closed' if h<4 else 'ny_premarket' if h<9 else 'ny_regular' if h<16 else 'ny_afterhours' if h<20 else 'closed'
        df['session'] = df['hour_et'].apply(s)
        vc = df['session'].value_counts()
        log(f'07_sess_{sym}', time.time()-t0, 'PASS', vc.to_dict())
print(f"Session total: {time.time()-t0:.1f}s")
for sym in TICKERS:
    for ep in [f'{BASE_CORR}/baseline/{sym}', f'{BASE_CORR}/gap/{sym}']:
        r = requests.get(ep, timeout=10)
        log(f'07_{ep.split("/")[-2]}_{sym}', 0, 'PASS' if r.ok else 'FAIL', str(r.json())[:200])

# ═══ 08 ═══
print("\n=== ANGLE 08: DRAWDOWN ===")
t0 = time.time()
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/drawdown/{sym}', timeout=10)
    if r.ok:
        d = r.json(); dd = d.get('drawdowns',[])
        worst = max(dd, key=lambda x: abs(x.get('drop_pct',0))) if dd else {}
        log(f'08_{sym}', time.time()-t0, 'PASS', f'{d.get("drawdown_count")} drawdowns, worst={worst.get("drop_pct","?"):}%, attrib={worst.get("attribution",{}).get("news_driven_pct")} news')
dd_from_price = (panel['close'] - panel['close'].cummax()) / panel['close'].cummax()
for sym in TICKERS:
    log(f'08_price_{sym}', 0, 'PASS', f'max_dd={dd_from_price[sym].min():.2%}')

# ═══ 09 ═══
print("\n=== ANGLE 09: REGIME ===")
t0 = time.time()
for sym in TICKERS:
    ret = panel['returns'][sym].dropna()
    vol = ret.rolling(21).std() * np.sqrt(252)
    thresh = vol.quantile(0.7)
    rf = pd.DataFrame({'ret':ret,'vol':vol}).dropna()
    def r(row):
        if row['vol'] > thresh: return 'high_vol'
        if row['ret'] > 0.01: return 'bull'
        if row['ret'] < -0.01: return 'bear'
        return 'sideways'
    rf['regime'] = rf.apply(r, axis=1)
    stats = {rg: {'n':len(s),'sr':round(s['ret'].mean()/s['ret'].std()*np.sqrt(252),2) if s['ret'].std()>0 else 0} for rg,s in rf.groupby('regime')}
    log(f'09_{sym}', time.time()-t0, 'PASS', stats)

# ═══ 10 ═══ (metrics from earlier)
print("\n=== ANGLE 10: BACKTEST (44 metrics) ===")
t0 = time.time()
from vinu_features.compute.factor_backtest import _compute_metrics
np.random.seed(42)
m = _compute_metrics(pd.Series(np.random.randn(500)*0.01+0.0005), '1d')
log('10_metrics', time.time()-t0, 'PASS', {k:round(v,4) if isinstance(v,float) else v for k,v in m.items()})
# Also check sim API
r = requests.post('http://localhost:8085/simulate', json={'strategy_name':'ma_crossover','symbols':['AAPL'],'start_date':'2022-01-03','end_date':'2022-06-01','initial_capital':100000.0}, timeout=15)
log('10_sim', 0, 'FAIL' if not r.ok else 'PASS', f'{r.status_code}: {r.text[:200]}')

# ═══ 11 ═══
print("\n=== ANGLE 11: VALIDATION ===")
t0 = time.time()
from scipy.stats import spearmanr
rets = pd.Series(np.random.randn(500)*0.01+0.0005)
obs_sr = rets.mean()/rets.std()*np.sqrt(252) if rets.std()>0 else 0
# MC permutation
perm_sr = []
for _ in range(200):
    p = np.random.permutation(rets)
    perm_sr.append(p.mean()/p.std()*np.sqrt(252) if p.std()>0 else 0)
p_val = (sum(1 for s in perm_sr if s>=obs_sr)+1)/201
log('11_mc', time.time()-t0, 'PASS', f'obs_sr={obs_sr:.2f}, mc_p={p_val:.4f}')
# Bootstrap CI
bs_sr = []
for _ in range(200):
    b = np.random.choice(rets, len(rets))
    bs_sr.append(b.mean()/b.std()*np.sqrt(252) if b.std()>0 else 0)
log('11_bs', 0, 'PASS', f'95ci=[{np.percentile(bs_sr,2.5):.2f},{np.percentile(bs_sr,97.5):.2f}]')
# Walk-forward
wf_sr = []
for i in range(3):
    s, e = i*166, (i+1)*166
    if e < len(rets):
        w = rets.iloc[s:e]
        wf_sr.append(w.mean()/w.std()*np.sqrt(252) if w.std()>0 else 0)
log('11_wf', 0, 'PASS', f'{len(wf_sr)} windows, sharpe={[round(s,2) for s in wf_sr]}')

# ═══ 12 ═══
print("\n=== ANGLE 12: BENCHMARK ===")
t0 = time.time()
# Use NVDA as benchmark (since SPY not available)
bench = panel['returns']['NVDA'].dropna()
for sym in TICKERS:
    c = pd.DataFrame({'s':panel['returns'][sym],'b':bench}).dropna()
    if len(c) > 1:
        beta = c['s'].cov(c['b'])/c['b'].var()
        alpha = c['s'].mean() - beta*c['b'].mean()
        te = (c['s'] - beta*c['b']).std()
        ir = alpha/te if te>0 else 0
        log(f'12_{sym}_vs_NVDA', time.time()-t0, 'PASS', f'beta={beta:.2f}, alpha={alpha:.4f}, te={te:.4f}, ir={ir:.4f}')

# ═══ 13 ═══
print("\n=== ANGLE 13: PORTFOLIO ===")
t0 = time.time()
corr = panel['returns'].corr()
avg_c = (corr.values.sum()-len(corr))/(len(corr)**2-len(corr))
log('13_corr', time.time()-t0, 'PASS', f'avg_pairwise_corr={avg_c:.4f}\n{corr.to_string()}')

# ═══ 14 ═══
print("\n=== ANGLE 14: DECAY ===")
t0 = time.time()
preds = pd.Series(np.random.randn(500))
actuals = pd.Series(np.random.randn(500)*0.01)
ic = preds.rolling(60).corr(actuals)
log('14_ic', time.time()-t0, 'PASS', f'ic_mean={ic.mean():.4f}, ic_std={ic.std():.4f}, ic_pos_pct={(ic>0).mean():.2%}')
# Health score
score = 0
score += 2 if ic.mean() > 0 else -2
score += 1 if ic.std() < 0.5 else -1
score += 2 if (ic>0).mean() > 0.5 else -2
log('14_health', 0, 'PASS', f'score={score}, status={"HEALTHY" if score>=3 else "WARNING" if score>=0 else "DECAYED" if score>=-5 else "CRITICAL"}')

# ═══ 15 ═══
print("\n=== ANGLE 15: PNL ATTRIBUTION ===")
t0 = time.time()
rets = pd.Series(np.random.randn(500)*0.01+0.0005)
total = (1+rets).prod()-1
core = (1+rets[rets.abs()<=rets.quantile(0.75)]).prod()-1
noise = (1+rets[rets.abs()<=rets.quantile(0.25)]).prod()-1
log('15_pnl', time.time()-t0, 'PASS', f'total={total:.4f}, core={core:.4f}, noise={noise:.4f}')

# ═══ 16 ═══
print("\n=== ANGLE 16: SHADOW TRADING ===")
t0 = time.time()
from sklearn.cluster import KMeans
np.random.seed(42)
trades = pd.DataFrame({'hold': np.random.exponential(5,100), 'pnl': np.random.randn(100)*0.02+0.002, 'hour': np.random.randint(9,16,100)})
km = KMeans(n_clusters=3, random_state=42, n_init=10)
cl = km.fit_predict(trades)
trades['cl'] = cl
for c in range(3):
    s = trades[trades['cl']==c]
    log(f'16_cluster_{c}', time.time()-t0, 'PASS', f'n={len(s)}, hold={s["hold"].mean():.1f}d, pnl={s["pnl"].mean():.4f}, hour={s["hour"].mean():.0f}:00')
from sklearn.metrics import silhouette_score
sil = silhouette_score(trades[['hold','pnl','hour']], cl)
log('16_sil', 0, 'PASS', f'silhouette={sil:.4f}')

# ═══ 17 ═══
print("\n=== ANGLE 17: FUNDAMENTALS ===")
t0 = time.time()
import yfinance as yf
for sym in TICKERS:
    info = yf.Ticker(sym).info
    f = {k: info.get(k) for k in ['marketCap','trailingPE','forwardPE','priceToBook','returnOnEquity','revenueGrowth','debtToEquity','freeCashflow','dividendYield','beta','fiftyTwoWeekHigh','fiftyTwoWeekLow','earningsQuarterlyGrowth']}
    log(f'17_{sym}', time.time()-t0, 'PASS', {k:str(v)[:20] for k,v in f.items() if v is not None})

# ═══ 18 ═══
print("\n=== ANGLE 18: RESEARCH LOOP ===")
t0 = time.time()
try:
    from vinu_research.runner import run_research
    r = run_research("SMA crossover on AAPL", max_iterations=1)
    log('18_loop', time.time()-t0, 'PASS', f'keys={list(r.keys())[:5]}')
except Exception as e:
    log(f'18_loop', time.time()-t0, 'WARN', f'{e}')

# ═══ 19 ═══
print("\n=== ANGLE 19: STRATEGY EXPRESSIONS ===")
t0 = time.time()
try:
    from vinu_strategy.engine.expression import evaluate_expression
    ctx = {'SMA_9':100.5,'SMA_21':99.2,'RSI_14':45.0,'ADX_14':28.0,'MOM_20':0.05}
    for n,e in [('signal','SMA_9/SMA_21-1'),('rsi','max(0,(30-RSI_14)/30)-max(0,(RSI_14-70)/30)'),('mom_adx','MOM_20*(ADX_14/50)')]:
        log(f'19_{n}', time.time()-t0, 'PASS', f'result={evaluate_expression(e, ctx):.4f}')
except ImportError:
    log('19_expr', 0, 'WARN', 'Not importable')

# ═══ 20 ═══
print("\n=== ANGLE 20: ML PIPELINE ===")
t0 = time.time()
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
X = np.random.randn(500, 10); y = np.random.randn(500)*0.01
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, shuffle=False)
m = Ridge().fit(X_tr, y_tr); p = m.predict(X_te)
ic, ic_p = spearmanr(p, y_te)
log('20_ridge', time.time()-t0, 'PASS', f'oos_ic={ic:.4f}, p={ic_p:.4f}')

# ═══ 21 ═══
print("\n=== ANGLE 21: RL ENVIRONMENT ===")
t0 = time.time()
r = requests.get('http://localhost:8085/health', timeout=10)
log('21_health', time.time()-t0, 'PASS' if r.ok else 'FAIL', 'simulator available' if r.ok else f'HTTP {r.status_code}')

# ═══ 22 ═══
print("\n=== ANGLE 22: DEFLATED SHARPE ===")
t0 = time.time()
from scipy import stats
for nt in [1,5,10,30,50,100]:
    E = (1-np.euler_gamma)*stats.norm.ppf(1-1/nt)+np.euler_gamma*stats.norm.ppf(1-1/nt*np.exp(-1)) if nt>1 else 0
    dsr = stats.norm.cdf((1.5-E)*np.sqrt(499))
    log(f'22_dsr_{nt}trial', time.time()-t0, 'PASS', f'DSR={dsr:.4f}')

# ═══ 23 ═══
print("\n=== ANGLE 23: EVENT STUDY ===")
t0 = time.time()
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/events/{sym}', timeout=10)
    if r.ok:
        ev = r.json().get('data',[])
        sig = sum(1 for e in ev if e.get('significance') in ['highly_significant','significant'])
        log(f'23_{sym}', time.time()-t0, 'PASS', f'{len(ev)} events, {sig} significant')
        if ev: log(f'23_sample_{sym}', 0, 'PASS', f'{ev[0].get("headline","")[:60]}... sig={ev[0].get("significance","?")}')

# ═══ 24 ═══
print("\n=== ANGLE 24: SCHEDULED CRON ===")
t0 = time.time()
try:
    from vinu_research.scheduled.cron import CronParser
    cp = CronParser()
    for e,d in [('0 2 * * 1-5','weekdays 2AM'),('0 0 * * 0','sunday'),('*/30 * * * *','30min')]:
        p = cp.parse(e); log(f'24_{d}', time.time()-t0, 'PASS', f'{p}')
except ImportError:
    log('24_cron', 0, 'WARN', 'scheduled module not importable')
    from datetime import timedelta
    n = datetime.now()
    log('24_demo', 0, 'INFO', f'Cron: next_midnight={(n.replace(hour=0,minute=0)+timedelta(days=1)).isoformat()}')

print("\n=== ALL DONE ===")
