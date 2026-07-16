"""Angle 16: Shadow Trading — K-Means clustering on real price return features."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

import requests
from datetime import datetime, timezone

BASE_PRICE = 'http://localhost:8081'
TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
FIRST_TS = 1641168000
NOW_TS = int(datetime.now(timezone.utc).timestamp())

try:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# ── Step 0: Fetch real OHLCV and build return features ──
print("=== STEP 0: FETCH REAL PRICE DATA ===")
t0 = time.time()
ohlcv = {}
for sym in TICKERS:
    try:
        r = requests.get(f'{BASE_PRICE}/candles/{sym}', params={
            'interval': '1d', 'from': FIRST_TS, 'to': NOW_TS
        }, timeout=30)
        if r.status_code == 200:
            data = r.json().get('data', [])
            df = pd.DataFrame(data)
            if not df.empty and 'close' in df.columns:
                df['return'] = df['close'].pct_change()
                df['volatility'] = df['return'].rolling(20).std()
                df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
                ohlcv[sym] = df
                log(f'fetch_{sym}', time.time()-t0, 'PASS', f'{len(df)} bars')
    except Exception as e:
        log(f'fetch_{sym}', time.time()-t0, 'FAIL', str(e))
log('fetch_all', time.time()-t0, 'DONE', f'{len(ohlcv)} tickers')

# ── Step 1: Build feature matrix from real returns ──
print("\n=== STEP 1: BUILD FEATURE MATRIX ===")
t0 = time.time()
features_list = []
labels_list = []
for sym in TICKERS:
    if sym in ohlcv:
        df = ohlcv[sym].dropna(subset=['return'])
        for _, row in df.iterrows():
            features_list.append({
                'ticker': sym,
                'return': row['return'],
                'volatility': row.get('volatility', 0) or 0,
                'volume_ratio': row.get('volume_ratio', 1) or 1,
            })
            labels_list.append(sym)
features_df = pd.DataFrame(features_list)
log('features', time.time()-t0, 'PASS', f'{len(features_df)} samples across {len(TICKERS)} tickers')

# ── Step 2: K-Means on real return features ──
print("\n=== STEP 2: K-MEANS CLUSTERING ===")
t0 = time.time()
if HAS_SKLEARN and len(features_df) > 0:
    X_raw = features_df[['return', 'volatility', 'volume_ratio']].dropna().values
    if len(X_raw) < 10:
        log('kmeans', 0, 'SKIP', 'Too few samples after NaN drop')
    else:
        X = StandardScaler().fit_transform(X_raw)
        for k in [2, 3, 4, 5]:
            t1 = time.time()
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X)
            sil = silhouette_score(X, labels)
            log(f'kmeans_k{k}', time.time()-t1, 'PASS', f'silhouette={sil:.4f}')
else:
    log('kmeans', 0, 'SKIP', 'sklearn not available')

# ── Step 3: Detailed Cluster Analysis (k=3) ──
print("\n=== STEP 3: CLUSTER ANALYSIS (k=3) ===")
t0 = time.time()
if HAS_SKLEARN and len(features_df) > 0:
    X_raw = features_df[['return', 'volatility', 'volume_ratio']].dropna().values
    if len(X_raw) < 10:
        log('cluster_analysis', 0, 'SKIP', 'Too few samples after NaN drop')
    else:
        X = StandardScaler().fit_transform(X_raw)
        km = KMeans(n_clusters=3, random_state=42, n_init=10)
        features_df = features_df.dropna(subset=['return', 'volatility', 'volume_ratio']).copy()
        features_df['cluster'] = km.fit_predict(X).tolist()
        sil = silhouette_score(X, features_df['cluster'])
        for c in sorted(features_df['cluster'].unique()):
            grp = features_df[features_df['cluster'] == c]
            tickers_in_cluster = grp['ticker'].value_counts().to_dict()
            log(f'cluster_{c}', time.time()-t0, 'PASS',
                f'n={len(grp)}, ret={grp["return"].mean():.4f}, '
                f'vol={grp["volatility"].mean():.4f}, tickers={tickers_in_cluster}')
        log('silhouette', time.time()-t0, 'PASS', f'score={sil:.4f}')
else:
    log('cluster_analysis', 0, 'SKIP', 'sklearn not available')

# ── Step 4: Cross-ticker similarity ──
print("\n=== STEP 4: TICKER CLUSTER OVERLAP ===")
t0 = time.time()
if HAS_SKLEARN and 'cluster' in features_df.columns:
    for sym in TICKERS:
        sym_data = features_df[features_df['ticker'] == sym]
        if len(sym_data) > 0:
            cluster_dist = sym_data['cluster'].value_counts(normalize=True).to_dict()
            log(f'ticker_{sym}', time.time()-t0, 'PASS',
                f'cluster_dist={cluster_dist}')
else:
    log('ticker_overlap', 0, 'SKIP', 'sklearn not available')

# ── Step 5: FIFO Roundtrip Pairing (synthetic only, no real fill data available) ──
print("\n=== STEP 5: FIFO ROUNDTRIP (real price-based) ===")
t0 = time.time()
roundtrips = []
for sym in TICKERS:
    if sym in ohlcv:
        df = ohlcv[sym].dropna(subset=['close'])
        for i in range(0, min(50, len(df) - 1), 2):
            if i + 1 >= len(df):
                break
            entry = df.iloc[i]
            exit_ = df.iloc[i + 1]
            pnl_pct = (exit_['close'] - entry['close']) / entry['close']
            roundtrips.append({
                'symbol': sym,
                'pnl_pct': pnl_pct,
                'holding_days': 1,
                'entry_date': str(entry.get('bar_ts', '')),
            })
rt_df = pd.DataFrame(roundtrips)
log('roundtrips', time.time()-t0, 'PASS', f'{len(rt_df)} roundtrips, avg_pnl={rt_df["pnl_pct"].mean():.4f}')

# ── Step 6: Cluster by Roundtrip Features ──
print("\n=== STEP 6: ROUNDTRIP CLUSTERING ===")
t0 = time.time()
if HAS_SKLEARN and len(rt_df) >= 3:
    rt_features = rt_df[['pnl_pct']].values
    if len(rt_features) >= 3:
        km_rt = KMeans(n_clusters=3, random_state=42, n_init=10)
        rt_df['cluster'] = km_rt.fit_predict(rt_features)
        rt_sil = silhouette_score(rt_features, rt_df['cluster'])
        for c in sorted(rt_df['cluster'].unique()):
            grp = rt_df[rt_df['cluster'] == c]
            log(f'rt_cluster_{c}', time.time()-t0, 'PASS',
                f'n={len(grp)}, pnl={grp["pnl_pct"].mean():.4f}')
        log('rt_silhouette', time.time()-t0, 'PASS', f'score={rt_sil:.4f}')
    else:
        log('rt_clustering', 0, 'SKIP', 'Too few roundtrips')
else:
    log('rt_clustering', 0, 'SKIP', 'sklearn not available')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 16 shadow trading finished')
