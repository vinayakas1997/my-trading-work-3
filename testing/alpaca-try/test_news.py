"""Test Alpaca News API."""
import requests, os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\.env')

key = os.environ['ALPACA_API_KEY']
secret = os.environ['ALPACA_API_SECRET']
base_url = os.environ.get('ALPACA_DATA_BASE_URL', 'https://data.alpaca.markets')

# Use the news endpoint
url = f'{base_url.rstrip("/")}/v1beta1/news'
headers = {
    'APCA-API-KEY-ID': key,
    'APCA-API-SECRET-KEY': secret,
}

params = {
    'symbols': 'AAPL',
    'limit': 5,
    'sort': 'desc',
}

resp = requests.get(url, params=params, headers=headers, timeout=30)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    news_list = data.get('news', [])
    print(f'News articles: {len(news_list)}')
    for article in news_list:
        print(f'  - [{article.get("source")}] {article.get("headline", "")[:80]}')
        print(f'    Created: {article.get("created_at", "")}')
else:
    print(f'Error: {resp.text[:500]}')

# Also probe news DB
import sqlite3
for db_path in [
    r'C:\Users\vinay\Desktop\my-trading-work-3\data\news\news.db',
    r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\data\news\news.db',
]:
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        print(f'\n=== DB: {db_path} ({os.path.getsize(db_path)} bytes) ===')
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cur.fetchall()]
        print(f'Tables: {tables}')
        for t in tables:
            cur.execute(f'SELECT COUNT(*) FROM {t}')
            cnt = cur.fetchone()[0]
            print(f'  {t}: {cnt} rows')
        con.close()
