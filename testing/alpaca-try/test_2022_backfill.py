"""Test full year 2022 1Min via IEX."""
import requests, os, copy
from dotenv import load_dotenv

load_dotenv(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\.env')

key = os.environ['ALPACA_API_KEY']
secret = os.environ['ALPACA_API_SECRET']
base_url = os.environ.get('ALPACA_DATA_BASE_URL', 'https://data.alpaca.markets')

url = base_url.rstrip('/') + '/v2/stocks/bars'
headers = {
    'APCA-API-KEY-ID': key,
    'APCA-API-SECRET-KEY': secret,
}

params = {
    'symbols': 'AAPL',
    'timeframe': '1Min',
    'start': '2022-01-01T00:00:00Z',
    'end': '2023-01-01T00:00:00Z',
    'limit': '10000',
    'feed': 'iex',
}
all_bars = []
page_token = None
for page in range(1, 50):
    p = copy.deepcopy(params)
    if page_token:
        p['page_token'] = page_token
    resp = requests.get(url, params=p, headers=headers, timeout=30)
    if resp.status_code == 403 and p.get('feed') == 'sip':
        p['feed'] = 'iex'
        resp = requests.get(url, params=p, headers=headers, timeout=30)
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

print(f'\nTotal {len(all_bars)} bars for 2022')
if all_bars:
    print(f'First: {all_bars[0]["t"]}')
    print(f'Last: {all_bars[-1]["t"]}')
