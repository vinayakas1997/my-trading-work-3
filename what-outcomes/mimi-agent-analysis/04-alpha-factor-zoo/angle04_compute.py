"""Part 2: Compute alpha factors via HTTP API (after discovering uppercase naming)."""
import requests, json, time, sys

BASE = 'http://localhost:8082'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(time.time())

def run(title, symbols, interval, features=None, preset=None):
    body = {'title': title, 'symbols': symbols, 'interval': interval, 'from': FIRST_TS, 'to': NOW_TS}
    if features: body['features'] = features
    if preset: body['preset'] = preset
    t0 = time.time()
    r = requests.post(f'{BASE}/requests', json=body, timeout=15)
    if r.status_code != 200:
        print(f'{title} CREATE FAIL: {r.status_code} {r.text[:200]}')
        return
    rid = r.json()['id']
    print(f'{title} create OK, id={rid}, create_time={time.time()-t0:.2f}s')
    t1 = time.time()
    r = requests.post(f'{BASE}/requests/{rid}/run', timeout=300)
    elapsed = time.time() - t1
    if r.status_code != 200:
        print(f'{title} RUN FAIL: {r.status_code} {r.text[:200]}')
        return
    res = r.json()
    print(f'{title} run OK: status={res.get("status")}, rows={res.get("row_count")}, compute_time={elapsed:.1f}s')
    return res

# 1) alpha101 preset across all 4 tickers
print('=== 1. alpha101 preset - 4 tickers, 1d ===')
run('alpha101_4T', TICKERS, '1d', preset='alpha101')

print()

# 2) gtja191 preset
print('=== 2. gtja191 preset - 4 tickers, 1d ===')
run('gtja191_4T', TICKERS, '1d', preset='gtja191')

print()

# 3) qlib158 preset
print('=== 3. qlib158 preset - 4 tickers, 1d ===')
run('qlib158_4T', TICKERS, '1d', preset='qlib158')

print()

# 4) Individual factors (uppercase)
print('=== 4. Individual factors - AAPL, 1d ===')
run('indiv_factors', ['AAPL'], '1d',
    features=['ALPHA101_001', 'ALPHA101_050', 'ALPHA101_101',
              'GTJA191_001', 'GTJA191_100',
              'QLIB158_MA5', 'QLIB158_ROC20'])

print()

# 5) Cross-timeframe alpha101
print('=== 5. alpha101 - AAPL, 1h ===')
run('alpha101_1h', ['AAPL'], '1h', preset='alpha101')

print()

print('=== 6. alpha101 - AAPL, 15m ===')
run('alpha101_15m', ['AAPL'], '15m', preset='alpha101')
