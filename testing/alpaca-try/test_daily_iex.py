"""Test earliest_available with IEX daily fallback."""
import requests, os, copy
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\.env')

key = os.environ['ALPACA_API_KEY']
secret = os.environ['ALPACA_API_SECRET']
base_url = os.environ.get('ALPACA_DATA_BASE_URL', 'https://data.alpaca.markets')

url = base_url.rstrip('/') + '/v2/stocks/bars'
headers = {
    'APCA-API-KEY-ID': key,
    'APCA-API-SECRET-KEY': secret,
}

for sym in ['AAPL', 'MSFT', 'NVDA', 'TSLA']:
    params = {
        'symbols': sym,
        'timeframe': '1Day',
        'start': '2020-01-01T00:00:00Z',
        'end': '2026-07-16T00:00:00Z',
        'limit': '10000',
    }
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code == 403 and params.get('feed') != 'iex':
        print(f'{sym}: 403 SIP, retrying IEX...')
        params['feed'] = 'iex'
        resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        bars = (data.get('bars') or {}).get(sym) or []
        if bars:
            yrs = set(b["t"][:4] for b in bars)
            print(f'{sym}: {len(bars)} daily bars, years={sorted(yrs)[:3]}...{sorted(yrs)[-1]}')
            print(f'  First bar: {bars[0]["t"]}')
        else:
            print(f'{sym}: 0 bars returned')
    else:
        print(f'{sym}: HTTP {resp.status_code} - {resp.text[:200]}')
