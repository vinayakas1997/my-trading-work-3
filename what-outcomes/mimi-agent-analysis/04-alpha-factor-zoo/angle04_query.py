import requests, json, time, os, sys
from datetime import datetime, timezone

BASE_FEATURES = 'http://localhost:8082'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

# ── Python API imports for factor browsing ──
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')
from vinu_features.compute.alpha_registry import Registry
from vinu_features.compute.bigger_recipe import catalog as recipe_catalog

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": detail}))

def check(label, elapsed, r, trunc=500):
    ok = 200 <= r.status_code < 300
    detail = ''
    if ok:
        try: data = r.json()
        except: data = r.text[:trunc]
        if isinstance(data, dict): detail = json.dumps(data, indent=2)[:trunc]
        elif isinstance(data, list): detail = f"{len(data)} items"
        else: detail = str(data)[:trunc]
    else:
        detail = f"HTTP {r.status_code}: {r.text[:300]}"
    log(label, elapsed, 'PASS' if ok else 'FAIL', detail)
    return ok, r

def run_features_request(title, symbols, interval, features):
    t0 = time.time()
    try:
        r = requests.post(f'{BASE_FEATURES}/requests', json={
            'title': title, 'symbols': symbols, 'interval': interval,
            'features': features, 'from': FIRST_TS, 'to': NOW_TS
        }, timeout=15)
    except Exception as e:
        log(f'{title}_create', time.time()-t0, 'FAIL', str(e))
        return None
    if r.status_code != 200:
        log(f'{title}_create', time.time()-t0, 'FAIL', f'HTTP {r.status_code}')
        return None
    req = r.json()
    rid = req.get('id')
    t1 = time.time()
    try:
        r2 = requests.post(f'{BASE_FEATURES}/requests/{rid}/run', timeout=120)
    except Exception as e:
        log(f'{title}_run', time.time()-t1, 'FAIL', str(e))
        return None
    if r2.status_code != 200:
        log(f'{title}_run', time.time()-t1, 'FAIL', f'HTTP {r2.status_code}')
        return None
    result = r2.json()
    log(f'{title}_run', round(time.time()-t1, 3),
        'PASS' if result.get('status') == 'done' else 'WARN',
        f'status={result.get("status")}, rows={result.get("row_count")}')
    return result

# ── Section 1: Enumerate Factor Registry ──
print("=== SECTION 1: FACTOR REGISTRY OVERVIEW ===")
t0 = time.time()
reg = Registry()
alk = reg.list_alphas()
log('registry_scan', time.time()-t0, 'PASS', f'Total factors: {reg.count()}')

# Factor families
families = {}
for a in alk:
    fam = a.meta.id.split('_')[0]  # alpha101_001 -> alpha101
    families[fam] = families.get(fam, 0) + 1
for fam, cnt in sorted(families.items()):
    log('family_' + fam, 0, 'INFO', f'{cnt} factors')

# Factor themes
themes = {}
for a in alk:
    th = a.meta.theme
    if isinstance(th, list):
        for t in th: themes[t] = themes.get(t, 0) + 1
    else:
        themes[th] = themes.get(th, 0) + 1
for th, cnt in sorted(themes.items()):
    log('theme_' + th, 0, 'INFO', f'{cnt} factors')

# ── Section 2: Browse Factor Metadata ──
print("\n=== SECTION 2: FACTOR METADATA SAMPLES ===")
for fid in ['alpha101_001', 'alpha101_050', 'alpha101_101',
            'gtja191_001', 'gtja191_100', 'gtja191_191',
            'qlib158_ma5', 'qlib158_roc20', 'qlib158_vma10',
            'academic_bab', 'academic_hml',
            'fundamental_roe', 'fundamental_asset_growth']:
    try:
        mod = reg.get(fid)
        if mod:
            m = mod.meta
            log(f'meta_{fid}', 0, 'INFO',
                f'theme={m.theme}, cols={m.columns_required}, '
                f'decay={m.decay_horizon}, warmup={m.min_warmup_bars}, '
                f'freq={m.frequency}, uni={m.universe}')
            log(f'formula_{fid}', 0, 'INFO', f'formula: {m.formula_latex[:200]}')
        else:
            log(f'meta_{fid}', 0, 'WARN', 'Not found in registry')
    except Exception as e:
        log(f'meta_{fid}', 0, 'FAIL', str(e))

# ── Section 3: Filter by Theme ──
print("\n=== SECTION 3: THEME DISTRIBUTION ===")
for theme_name in ['momentum', 'reversal', 'volatility', 'value', 'growth',
                    'quality', 'size', 'liquidity', 'sentiment',
                    'seasonality', 'volume', 'microstructure', 'other']:
    matched = [a for a in alk if (isinstance(a.meta.theme, list) and theme_name in a.meta.theme) or a.meta.theme == theme_name]
    log(f'theme_{theme_name}', 0, 'INFO', f'{len(matched)} factors')

# ── Section 4: Filter by Universe ──
print("\n=== SECTION 4: UNIVERSE DISTRIBUTION ===")
universes = {}
for a in alk:
    u = a.meta.universe
    if isinstance(u, list):
        for uu in u: universes[uu] = universes.get(uu, 0) + 1
    else:
        universes[u] = universes.get(u, 0) + 1
for u, cnt in sorted(universes.items()):
    log(f'universe_{u}', 0, 'INFO', f'{cnt} factors')

# ── Section 5: Decay Horizon Stats ──
print("\n=== SECTION 5: DECAY HORIZON DISTRIBUTION ===")
decay_buckets = {1: 0, 5: 0, 10: 0, 20: 0, 60: 0, 252: 0, 'other': 0}
for a in alk:
    dh = a.meta.decay_horizon
    found = False
    for bucket in decay_buckets:
        if dh == bucket:
            decay_buckets[bucket] += 1
            found = True
            break
    if not found:
        decay_buckets['other'] += 1
log('decay_distribution', 0, 'INFO', str(decay_buckets))

# ── Section 6: Compute Sample Factors ──
print("\n=== SECTION 6: COMPUTE SAMPLE FACTORS ===")
# Test individual factors
sample_factors = ['alpha101_001', 'alpha101_005', 'alpha101_010',
                  'sma_20', 'rsi_14', 'macd']
for sym in ['AAPL', 'NVDA']:
    t0 = time.time()
    result = run_features_request(f'factor_sample_{sym}', [sym], '1d', sample_factors)
    if result:
        log(f'factor_sample_{sym}_outcome', 0, 'PASS',
            f'rows={result.get("row_count")}')

# ── Section 7: Compute Full alpha101 Preset ──
print("\n=== SECTION 7: FULL ALPHA101 PRESET ===")
t0 = time.time()
result = run_features_request('alpha101_full', ['AAPL'], '1d', ['alpha101'])
if result:
    log('alpha101_full_outcome', 0, 'INFO',
        f'rows={result.get("row_count")}, status={result.get("status")}')

# ── Section 8: Recipe Presets ──
print("\n=== SECTION 8: RECIPE PRESETS ===")
for rname in recipe_catalog.list_recipe_names():
    meta = recipe_catalog.get_recipe_meta(rname)
    log(f'recipe_{rname}', 0, 'INFO',
        f'warmup={meta.get("warmup_bars", "?")}, '
        f'desc={meta.get("description", "?")[:100]}')
    # Compute each recipe
    result = run_features_request(rname, ['AAPL'], '1d', [rname])
    if result:
        log(f'recipe_{rname}_outcome', 0, 'INFO',
            f'rows={result.get("row_count")}')

# ── Section 9: Summary ──
print("\n=== SECTION 9: SUMMARY ===")
log('total', 0, 'DONE',
    f'Angle 04: Alpha Factor Zoo complete. {reg.count()} total factors browsed.')
