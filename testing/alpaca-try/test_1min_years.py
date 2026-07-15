"""Test earliest 1Min data available on IEX."""
import requests, os
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

sym = 'AAPL'

# Probe 1Min each year to find earliest
for year in range(2020, 2026):
    params = {
        'symbols': sym,
        'timeframe': '1Min',
        'start': f'{year}-01-01T00:00:00Z',
        'end': f'{year}-02-01T00:00:00Z',
        'limit': '5',
        'feed': 'iex',
    }
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        bars = (data.get('bars') or {}).get(sym) or []
        if bars:
            print(f'{year}: {len(bars)} bars, first={bars[0]["t"]}')
        else:
            print(f'{year}: 0 bars (no data)')
    else:
        print(f'{year}: HTTP {resp.status_code}')
