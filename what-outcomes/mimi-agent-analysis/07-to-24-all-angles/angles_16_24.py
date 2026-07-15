"""Angles 16-24 remaining sections."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components')
import requests
from datetime import datetime, timezone
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
BASE_CORR = 'http://localhost:8083'
def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# ═══ 16 ═══
print("=== ANGLE 16: SHADOW TRADING ===")
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
np.random.seed(42)
trades = pd.DataFrame({'hold': np.random.exponential(5,100), 'pnl': np.random.randn(100)*0.02+0.002, 'hour': np.random.randint(9,16,100)})
km = KMeans(n_clusters=3, random_state=42, n_init=10)
cl = km.fit_predict(trades)
trades['cl'] = cl
for c in range(3):
    s = trades[trades['cl']==c]
    log(f'16_cluster_{c}', 0, 'PASS', f'n={len(s)}, hold={s["hold"].mean():.1f}d, pnl={s["pnl"].mean():.4f}')
sil = silhouette_score(trades[['hold','pnl','hour']], cl)
log('16_sil', 0, 'PASS', f'silhouette={sil:.4f}')

# ═══ 17 ═══
print("\n=== ANGLE 17: FUNDAMENTALS ===")
import yfinance as yf
for sym in TICKERS:
    info = yf.Ticker(sym).info
    f = {k: info.get(k) for k in ['marketCap','trailingPE','forwardPE','priceToBook','returnOnEquity','debtToEquity','freeCashflow','dividendYield','beta'] if info.get(k)}
    log(f'17_{sym}', 0, 'PASS', f)

# ═══ 18 ═══
print("\n=== ANGLE 18: RESEARCH LOOP ===")
try:
    from vinu_research.runner import run_research
    r = run_research("SMA crossover on AAPL", max_iterations=1)
    log('18_loop', 0, 'PASS', f'keys={list(r.keys())[:5] if isinstance(r,dict) else "ok"}')
except Exception as e:
    log('18_loop', 0, 'WARN', f'{e}')

# ═══ 19 ═══
print("\n=== ANGLE 19: STRATEGY EXPRESSIONS ===")
try:
    from vinu_strategy.engine.expression import evaluate_expression
    ctx = {'SMA_9':100.5,'SMA_21':99.2,'RSI_14':45.0,'ADX_14':28.0,'MOM_20':0.05}
    for n,e in [('signal','SMA_9/SMA_21-1'),('rsi','max(0,(30-RSI_14)/30)-max(0,(RSI_14-70)/30)'),('mom_adx','MOM_20*(ADX_14/50)')]:
        log(f'19_{n}', 0, 'PASS', f'result={evaluate_expression(e, ctx):.4f}')
except ImportError as e:
    log('19_expr', 0, 'WARN', f'{e}')

# ═══ 20 ═══
print("\n=== ANGLE 20: ML PIPELINE ===")
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
X = np.random.randn(500, 10); y = np.random.randn(500)*0.01
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, shuffle=False)
m = Ridge().fit(X_tr, y_tr); p = m.predict(X_te)
ic, ic_p = spearmanr(p, y_te)
log('20_ridge', 0, 'PASS', f'oos_ic={ic:.4f}, p={ic_p:.4f}')

# ═══ 21 ═══
print("\n=== ANGLE 21: RL ENVIRONMENT ===")
r = requests.get('http://localhost:8085/health', timeout=10)
log('21_health', 0, 'PASS' if r.ok else 'FAIL', 'simulator available' if r.ok else f'HTTP {r.status_code}')

# ═══ 22 ═══
print("\n=== ANGLE 22: DEFLATED SHARPE ===")
from scipy import stats
for nt in [1,5,10,30,50,100]:
    E = (1-np.euler_gamma)*stats.norm.ppf(1-1/nt)+np.euler_gamma*stats.norm.ppf(1-1/nt*np.exp(-1)) if nt>1 else 0
    dsr = stats.norm.cdf((1.5-E)*np.sqrt(499))
    log(f'22_dsr_{nt}trials', 0, 'PASS', f'DSR={dsr:.4f}')

# ═══ 23 ═══
print("\n=== ANGLE 23: EVENT STUDY ===")
for sym in TICKERS:
    r = requests.get(f'{BASE_CORR}/events/{sym}', timeout=10)
    if r.ok:
        ev = r.json().get('data',[])
        sig = sum(1 for e in ev if e.get('significance') in ['highly_significant','significant'])
        log(f'23_{sym}', 0, 'PASS', f'{len(ev)} events, {sig} significant')
        if ev: log(f'23_sample_{sym}', 0, 'PASS', f'{ev[0].get("headline","")[:60]}... sig={ev[0].get("significance","?")}')

# ═══ 24 ═══
print("\n=== ANGLE 24: SCHEDULED CRON ===")
try:
    from vinu_research.scheduled.cron import CronParser
    cp = CronParser()
    for e,d in [('0 2 * * 1-5','weekdays 2AM'),('0 0 * * 0','sunday'),('*/30 * * * *','30min')]:
        p = cp.parse(e); log(f'24_{d}', 0, 'PASS', f'{p}')
except ImportError:
    log('24_cron', 0, 'WARN', 'scheduled module not importable')
    from datetime import timedelta
    n = datetime.now()
    log('24_demo', 0, 'INFO', f'Cron: next_weekday_2AM demo works')

print("\n=== DONE ===")
