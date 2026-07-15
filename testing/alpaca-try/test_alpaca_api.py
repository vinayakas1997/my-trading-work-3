"""Test the Alpaca v2 bars endpoint (same as vinu-stock-provider uses)."""
import requests, os
from dotenv import load_dotenv

load_dotenv(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\.env')

key = os.environ.get('ALPACA_API_KEY', '')
secret = os.environ.get('ALPACA_API_SECRET', '')
base_url = os.environ.get('ALPACA_DATA_BASE_URL', 'https://data.alpaca.markets')

print(f'Using key: {key[:8]}...{key[-4:]}')
print(f'Base URL: {base_url}')

# Try v2/bars endpoint (what the provider uses)
url = f'{base_url.rstrip("/")}/v2/stocks/bars'
params = {
    'symbols': 'AAPL',
    'timeframe': '1Day',
    'start': '2023-01-01T00:00:00Z',
    'end': '2023-01-10T00:00:00Z',
    'limit': '10',
    'adjustment': 'raw'
}
headers = {
    'APCA-API-KEY-ID': key,
    'APCA-API-SECRET-KEY': secret,
}

resp = requests.get(url, params=params, headers=headers, timeout=30)
print(f'Status: {resp.status_code}')
print(f'URL: {resp.url}')
if resp.status_code == 200:
    data = resp.json()
    bars = (data.get('bars') or {}).get('AAPL') or []
    print(f'Bars returned: {len(bars)}')
    if bars:
        print('First bar:', bars[0])
    else:
        print('Full response keys:', list(data.keys()))
        print(f'Response: {str(data)[:1000]}')
else:
    print(f'Error: {resp.text[:1000]}')
