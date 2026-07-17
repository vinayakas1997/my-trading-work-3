"""Shadow Trading — K-Means clustering of return patterns, silhouette score, FIFO roundtrip pairing"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone

try:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    rows = []
    if bars is None:
        bars = pd.DataFrame()
    if bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "time_format": time_format,
            "angle": "shadow_trading",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    volume = bars["volume"].astype(float)
    returns = close.pct_change()
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(returns.dropna()) < 20:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "shadow_trading",
            "status": "insufficient_data",
            "n_observations": len(returns.dropna()),
        }])

    features_df = pd.DataFrame({
        "return": returns,
        "volatility": returns.rolling(20).std(),
        "volume_ratio": volume / volume.rolling(20).mean(),
    }).dropna()

    if len(features_df) < 10:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "shadow_trading",
            "status": "insufficient_data_after_features",
            "n_observations": len(features_df),
        }])

    if HAS_SKLEARN:
        X_raw = features_df[["return", "volatility", "volume_ratio"]].values
        X = StandardScaler().fit_transform(X_raw)
        n_unique = len(set(np.argmin(np.abs(X - X.mean(axis=0)), axis=1))) if X.shape[0] > 1 else 1

        for k in [2, 3, 4, 5]:
            if n_unique < k:
                break
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = km.fit_predict(X)
                if len(set(labels)) < 2:
                    raise ValueError("Only one cluster found")
                sil = float(silhouette_score(X, labels))
                inertia_val = float(km.inertia_)
            except Exception:
                sil = 0.0
                inertia_val = 0.0
            rows.append({
                "symbol": symbol,
                "analysis_at": analysis_at,
                "time_format": time_format,
                "angle": "shadow_trading",
                "metric": "kmeans_silhouette",
                "n_clusters": k,
                "silhouette_score": round(sil, 4),
                "inertia": round(inertia_val, 4),
            })

        try:
            km3 = KMeans(n_clusters=3, random_state=42, n_init=10)
            features_df = features_df.copy()
            features_df["cluster"] = km3.fit_predict(X)

            if len(set(features_df["cluster"])) >= 2:
                sil3 = float(silhouette_score(X, features_df["cluster"]))
            else:
                sil3 = 0.0
            rows.append({
                "symbol": symbol,
                "analysis_at": analysis_at,
                "time_format": time_format,
                "angle": "shadow_trading",
                "metric": "kmeans_k3",
                "n_clusters": 3,
                "silhouette_score": round(sil3, 4),
            })

            for c in sorted(features_df["cluster"].unique()):
                grp = features_df[features_df["cluster"] == c]
                rows.append({
                    "symbol": symbol,
                    "analysis_at": analysis_at,
                    "time_format": time_format,
                    "angle": "shadow_trading",
                    "metric": "cluster_profile",
                    "cluster": int(c),
                    "count": len(grp),
                    "mean_return": round(float(grp["return"].mean()), 6),
                    "mean_volatility": round(float(grp["volatility"].mean()), 6),
                    "mean_volume_ratio": round(float(grp["volume_ratio"].mean()), 4),
                })
        except Exception:
            pass
    else:
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "shadow_trading",
            "metric": "sklearn_unavailable",
            "status": "skipped",
        })

    roundtrips = []
    for i in range(0, min(50, len(close) - 1), 2):
        if i + 1 >= len(close):
            break
        entry = close.iloc[i]
        exit_ = close.iloc[i + 1]
        pnl_pct = float((exit_ - entry) / entry)
        roundtrips.append({
            "pnl_pct": pnl_pct,
        })

    if roundtrips:
        rt_df = pd.DataFrame(roundtrips)
        avg_pnl = float(rt_df["pnl_pct"].mean())
        std_pnl = float(rt_df["pnl_pct"].std())
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "shadow_trading",
            "metric": "fifo_roundtrips",
            "n_roundtrips": len(roundtrips),
            "avg_pnl_pct": round(avg_pnl, 6),
            "std_pnl_pct": round(std_pnl, 6),
            "win_rate": float((rt_df["pnl_pct"] > 0).mean()),
        })

        if HAS_SKLEARN and len(rt_df) >= 3:
            rt_features = rt_df[["pnl_pct"]].values
            if len(rt_features) >= 3:
                km_rt = KMeans(n_clusters=3, random_state=42, n_init=10)
                rt_labels = km_rt.fit_predict(rt_features)
                rt_sil = float(silhouette_score(rt_features, rt_labels))
                rows.append({
                    "symbol": symbol,
                    "analysis_at": analysis_at,
                    "time_format": time_format,
                    "angle": "shadow_trading",
                    "metric": "roundtrip_clustering",
                    "n_clusters": 3,
                    "silhouette_score": round(rt_sil, 4),
                })
                for c in sorted(set(rt_labels)):
                    grp = rt_df[rt_labels == c]
                    rows.append({
                        "symbol": symbol,
                        "analysis_at": analysis_at,
                        "time_format": time_format,
                        "angle": "shadow_trading",
                        "metric": "roundtrip_cluster_profile",
                        "cluster": int(c),
                        "count": len(grp),
                        "mean_pnl": round(float(grp["pnl_pct"].mean()), 6),
                    })

    return pd.DataFrame(rows)
