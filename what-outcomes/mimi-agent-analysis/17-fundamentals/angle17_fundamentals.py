"""Angle 17: Fundamentals — PE, ROE, market cap, FCF, dividend yield via Alpaca API."""
import sys, json, time
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

# Alpaca credentials
ALPACA_KEY = 'PKRTEIQX45ZWBBJXFZ7RMFICOV'
ALPACA_SECRET = '51Y3yL5kYkqU29pEHtXcrAgYsHcQ8Gt5VFXNgvrk4hWa'
ALPACA_HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# ── Step 1: Alpaca News API (source check) ──
print("=== STEP 1: ALPACA SOURCE CHECK ===")
t0 = time.time()
try:
    r = requests.get('https://data.alpaca.markets/v1beta1/news', params={
        'symbols': 'AAPL', 'limit': 1, 'include_content': 'false'
    }, headers=ALPACA_HEADERS, timeout=15)
    if r.status_code == 200:
        d = r.json()
        log('alpaca_connect', time.time()-t0, 'PASS', f'News API works, found {len(d.get("news",[]))} articles')
    else:
        log('alpaca_connect', time.time()-t0, 'FAIL', f'HTTP {r.status_code}: {r.text[:200]}')
except Exception as e:
    log('alpaca_connect', time.time()-t0, 'FAIL', str(e))

# ── Step 2: Alpaca Corporate Actions (dividends/splits) ──
print("\n=== STEP 2: CORPORATE ACTIONS ===")
t0 = time.time()
for sym in TICKERS:
    t1 = time.time()
    try:
        r = requests.get('https://data.alpaca.markets/v1/corporate-actions', params={
            'symbols': sym, 'types': 'cash_dividend', 'limit': 5,
            'start': '2024-01-01', 'end': '2026-07-16'
        }, headers=ALPACA_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get('corporate_actions', {})
            dividends = data.get('cash_dividends', [])
            log(f'corp_actions_{sym}', time.time()-t1, 'PASS', f'{len(dividends)} dividend events')
            for a in dividends[:2]:
                rate = a.get('rate', '?')
                ex_date = a.get('ex_date', '?')
                log(f'dividend_{sym}', 0, 'INFO', f'${rate} on {ex_date}')
        else:
            log(f'corp_actions_{sym}', time.time()-t1, 'FAIL', f'HTTP {r.status_code}')
    except Exception as e:
        log(f'corp_actions_{sym}', time.time()-t1, 'FAIL', str(e))

# ── Step 3: yfinance fundamentals (used by vinu-stock-price internally) ──
print("\n=== STEP 3: FUNDAMENTALS ===")
t0 = time.time()
try:
    import yfinance as yf
    has_yf = True
except ImportError:
    has_yf = False
    log('yfinance', 0, 'WARN', 'yfinance not available')

if has_yf:
    for sym in TICKERS:
        t1 = time.time()
        try:
            tk = yf.Ticker(sym)
            info = tk.info
            fundamentals = {
                'marketCap': info.get('marketCap'),
                'trailingPE': info.get('trailingPE'),
                'forwardPE': info.get('forwardPE'),
                'priceToBook': info.get('priceToBook'),
                'returnOnEquity': info.get('returnOnEquity'),
                'revenueGrowth': info.get('revenueGrowth'),
                'debtToEquity': info.get('debtToEquity'),
                'freeCashflow': info.get('freeCashflow'),
                'dividendYield': info.get('dividendYield'),
                'beta': info.get('beta'),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),
                'earningsQuarterlyGrowth': info.get('earningsQuarterlyGrowth'),
                'profitMargins': info.get('profitMargins'),
                'returnOnAssets': info.get('returnOnAssets'),
                'revenuePerShare': info.get('revenuePerShare'),
                'totalRevenue': info.get('totalRevenue'),
                'operatingMargins': info.get('operatingMargins'),
                'bookValue': info.get('bookValue'),
                'priceToSalesTrailing12Months': info.get('priceToSalesTrailing12Months'),
            }
            clean = {k: v for k, v in fundamentals.items() if v is not None}
            log(f'fundamentals_{sym}', time.time()-t1, 'PASS', clean)
        except Exception as e:
            log(f'fundamentals_{sym}', time.time()-t1, 'FAIL', str(e))
else:
    for sym in TICKERS:
        log(f'fundamentals_{sym}', 0, 'SKIP', 'yfinance not installed')

# ── Step 4: Vinu-Stock-Price Catalog ──
print("\n=== STEP 4: STOCK PRICE CATALOG ===")
t0 = time.time()
try:
    r = requests.get('http://localhost:8081/catalog', timeout=10)
    if r.status_code == 200:
        log('catalog', time.time()-t0, 'PASS', f'Catalog: {str(r.json())[:500]}')
    else:
        log('catalog', time.time()-t0, 'FAIL', f'HTTP {r.status_code}')
except Exception as e:
    log('catalog', time.time()-t0, 'FAIL', str(e))

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 17 fundamentals finished')
