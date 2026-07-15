"""Test Alpaca daily bars availability for AAPL."""
import requests, os
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

# Test daily bars from 2020 to now
params = {
    'symbols': 'AAPL',
    'timeframe': '1Day',
    'start': '2020-01-01T00:00:00Z',
    'end': '2026-07-16T00:00:00Z',
    'limit': '10000',
}
resp = requests.get(url, params=params, headers=headers, timeout=30)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    bars = (data.get('bars') or {}).get('AAPL') or []
    print(f'Total daily bars: {len(bars)}')
    if bars:
        print(f'First: {bars[0]["t"]}')
        print(f'Last: {bars[-1]["t"]}')
        yrs = set(b["t"][:4] for b in bars)
        print(f'Years: {sorted(yrs)}')
else:
    print(f'Error: {resp.text[:300]}')

# Also test 2023 1Min to confirm it's available
params2 = {
    'symbols': 'AAPL',
    'timeframe': '1Min',
    'start': '2023-01-01T00:00:00Z',
    'end': '2023-06-01T00:00:00Z',
    'limit': '10000',
}
resp2 = requests.get(url, params=params2, headers=headers, timeout=60)
print(f'\n1Min 2023 H1 status: {resp2.status_code}')
if resp2.status_code == 200:
    data2 = resp2.json()
    bars2 = (data2.get('bars') or {}).get('AAPL') or []
    print(f'1Min 2023 H1 bars: {len(bars2)}')
    if bars2:
        print(f'First: {bars2[0]["t"]}')
        print(f'Last: {bars2[-1]["t"]}')
