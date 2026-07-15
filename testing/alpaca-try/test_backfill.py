"""Test the exact Alpaca fetch_bars flow the backfill uses."""
import requests, os, json
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\.env')

key = os.environ['ALPACA_API_KEY']
secret = os.environ['ALPACA_API_SECRET']
base_url = os.environ.get('ALPACA_DATA_BASE_URL', 'https://data.alpaca.markets')

url = f'{base_url.rstrip("/")}/v2/stocks/bars'
headers = {
    'APCA-API-KEY-ID': key,
    'APCA-API-SECRET-KEY': secret,
}

# Test with 1Min timeframe (what backfill uses)
print("=== Test 1: 1Min data for 1 day ===")
params = {
    'symbols': 'AAPL',
    'timeframe': '1Min',
    'start': '2023-01-03T09:00:00Z',
    'end': '2023-01-03T21:00:00Z',
    'limit': '10000',
}
resp = requests.get(url, params=params, headers=headers, timeout=30)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    bars = (data.get('bars') or {}).get('AAPL') or []
    print(f'Bars returned: {len(bars)}')
    print(f'Has next_page_token: {data.get("next_page_token")}')
    if bars:
        print(f'First: {bars[0]["t"]}')
        print(f'Last: {bars[-1]["t"]}')

print("\n=== Test 2: 1Min data with pagination ===")
params = {
    'symbols': 'AAPL',
    'timeframe': '1Min',
    'start': '2023-01-03T00:00:00Z',
    'end': '2023-01-10T00:00:00Z',
    'limit': '10000',
}
resp = requests.get(url, params=params, headers=headers, timeout=30)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    bars = (data.get('bars') or {}).get('AAPL') or []
    print(f'Bars (page 1): {len(bars)}')
    next_token = data.get("next_page_token")
    print(f'next_page_token: {next_token!r}')
    if next_token:
        print(f'next_page_token type: {type(next_token).__name__}')
        # Simulate page 2
        params2 = dict(params)
        params2['page_token'] = next_token
        resp2 = requests.get(url, params=params2, headers=headers, timeout=30)
        data2 = resp2.json()
        bars2 = (data2.get('bars') or {}).get('AAPL') or []
        print(f'Bars (page 2): {len(bars2)}')
        next_token2 = data2.get("next_page_token")
        print(f'next_page_token (page 2): {next_token2!r}')

print("\nDone")
