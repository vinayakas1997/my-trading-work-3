"""Test full year 1Min AAPL via pagination with IEX fallback."""
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

sym = 'AAPL'
# Test year 2024
start_iso = '2024-01-01T00:00:00Z'
end_iso = '2025-01-01T00:00:00Z'
params = {
    'symbols': sym,
    'timeframe': '1Min',
    'start': start_iso,
    'end': end_iso,
    'limit': '10000',
}

all_bars = []
page = 0
page_token = None
while True:
    page += 1
    p = copy.deepcopy(params)
    if page_token:
        p['page_token'] = page_token
    if page > 20:
        print("Too many pages, stopping")
        break
    resp = requests.get(url, params=p, headers=headers, timeout=30)
    # Simulate IEX fallback
    if resp.status_code == 403 and p.get('feed') != 'iex':
        print(f'Page {page}: 403 SIP, retrying with IEX')
        p['feed'] = 'iex'
        resp = requests.get(url, params=p, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f'Page {page}: HTTP {resp.status_code} - {resp.text[:200]}')
        break
    data = resp.json()
    bars = (data.get('bars') or {}).get(sym) or []
    all_bars.extend(bars)
    page_token = data.get('next_page_token')
    print(f'Page {page}: {len(bars)} bars, next_token={page_token!r}')
    if not page_token:
        break

print(f'\nTotal: {len(all_bars)} bars')
if all_bars:
    print(f'First: {all_bars[0]["t"]}')
    print(f'Last: {all_bars[-1]["t"]}')
