"""Test earliest_available logic."""
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

print(f'Fetching 1Min AAPL: {start_iso} to {end_iso}')

params = {
    'symbols': 'AAPL',
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
    if page_token:
        params['page_token'] = page_token
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f'Page {page}: HTTP {resp.status_code} - {resp.text[:200]}')
        break
    data = resp.json()
    bars = (data.get('bars') or {}).get('AAPL') or []
    all_bars.extend(bars)
    page_token = data.get('next_page_token')
    print(f'Page {page}: {len(bars)} bars, next_token={page_token!r}')
    if not page_token:
        break

print(f'\nTotal: {len(all_bars)} bars')
if all_bars:
    print(f'First timestamp: {all_bars[0]["t"]}')
    print(f'Last timestamp: {all_bars[-1]["t"]}')
    print(f'Earliest year: {all_bars[0]["t"][:4]}')
