"""Debug: Check available presets and feature naming conventions."""
import requests

BASE = 'http://localhost:8082'

r = requests.get(f'{BASE}/presets', timeout=10)
data = r.json().get('data', [])
print('=== Presets available ===')
for p in data:
    print(f'  {p["name"]}: {len(p.get("features", []))} features')

r2 = requests.get(f'{BASE}/presets/alpha101', timeout=10)
if r2.status_code == 200:
    p = r2.json()
    features = p.get('features', [])
    print(f'\n=== alpha101 preset ===')
    print(f'Feature count: {len(features)}')
    print(f'First 3: {features[:3]}')
    print(f'Last 3: {features[-3:]}')

r3 = requests.get(f'{BASE}/presets/gtja191', timeout=10)
print(f'\ngtja191 GET: {r3.status_code} {r3.text[:200]}')

r4 = requests.get(f'{BASE}/presets/qlib158', timeout=10)
print(f'qlib158 GET: {r4.status_code} {r4.text[:200]}')

print('\n=== Full preset names ===')
for p in data:
    print(f'  "{p["name"]}"')
