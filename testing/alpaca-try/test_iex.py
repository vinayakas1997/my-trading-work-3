"""Test Alpaca 1Min with IEX feed fallback."""
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

end_ts = int(datetime.now(timezone.utc).timestamp())
start_ts = end_ts - 365 * 24 * 3600
start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
end_iso = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

print(f'=== Test: 1Min with feed=iex ===')
print(f'Range: {start_iso} to {end_iso}')
params = {
    'symbols': 'AAPL',
    'timeframe': '1Min',
    'start': start_iso,
    'end': end_iso,
    'feed': 'iex',
    'limit': '10000',
}
resp = requests.get(url, params=params, headers=headers, timeout=30)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    bars = (data.get('bars') or {}).get('AAPL') or []
    print(f'Bars: {len(bars)}')
    if bars:
        print(f'First: {bars[0]["t"]}')
        print(f'Last: {bars[-1]["t"]}')
else:
    print(f'Error: {resp.text[:300]}')

print(f'\n=== Test: 1Min with no feed (default SIP), year 2023 only ===')
params2 = {
    'symbols': 'AAPL',
    'timeframe': '1Min',
    'start': '2023-01-01T00:00:00Z',
    'end': '2024-01-01T00:00:00Z',
    'limit': '10000',
}
resp2 = requests.get(url, params=params2, headers=headers, timeout=30)
print(f'Status: {resp2.status_code}')
if resp2.status_code == 200:
    data2 = resp2.json()
    bars2 = (data2.get('bars') or {}).get('AAPL') or []
    print(f'Bars: {len(bars2)}')
    if bars2:
        print(f'First: {bars2[0]["t"]}')
        print(f'Last: {bars2[-1]["t"]}')
else:
    print(f'Error: {resp2.text[:300]}')
