"""Test additional presets: alpha158, alpha360, and cross-timeframe."""
import requests, time

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
        print(f'FAIL {title}: {r.status_code} {r.text[:200]}')
        return None
    rid = r.json()['id']
    print(f'OK {title}: id={rid}')
    t1 = time.time()
    r = requests.post(f'{BASE}/requests/{rid}/run', timeout=300)
    elapsed = time.time() - t1
    if r.status_code != 200:
        print(f'FAIL {title}_run: {r.status_code} {r.text[:200]}')
        return None
    res = r.json()
    print(f'DONE {title}: status={res.get("status")}, rows={res.get("row_count")}, time={elapsed:.1f}s')
    return res

# Present in catalog but HUGE
print('=== alpha158 1T 1d ===')
run('alpha158_AAPL', ['AAPL'], '1d', preset='alpha158')

print()
print('=== alpha360 1T 1d ===')
run('alpha360_AAPL', ['AAPL'], '1d', preset='alpha360')

print()
print('=== alpha101 4T 1h ===')
run('alpha101_4T_1h', TICKERS, '1h', preset='alpha101')

print()
print('=== alpha101 4T 15m ===')
run('alpha101_4T_15m', TICKERS, '15m', preset='alpha101')
