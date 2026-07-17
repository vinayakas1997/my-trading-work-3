"""ML Model Pipeline — train/evaluate multiple models with OOS IC"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone

try:
    from scipy.stats import spearmanr
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def _try_model(name: str, X_tr, y_tr, X_te, y_te):
    t1 = datetime.now(timezone.utc)
    try:
        if name == "ridge":
            from sklearn.linear_model import Ridge
            m = Ridge(alpha=1.0).fit(X_tr, y_tr)
        elif name == "random_forest":
            from sklearn.ensemble import RandomForestRegressor
            m = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42).fit(X_tr, y_tr)
        elif name == "xgboost":
            import xgboost as xgb
            m = xgb.XGBRegressor(n_estimators=50, max_depth=5, verbosity=0).fit(X_tr, y_tr)
        elif name == "lightgbm":
            import lightgbm as lgb
            m = lgb.LGBMRegressor(n_estimators=50, max_depth=5, verbose=-1).fit(X_tr, y_tr)
        elif name == "catboost":
            from catboost import CatBoostRegressor
            m = CatBoostRegressor(n_estimators=50, max_depth=5, verbose=0, random_seed=42).fit(X_tr, y_tr)
        elif name == "elastic_net":
            from sklearn.linear_model import ElasticNet
            m = ElasticNet(alpha=0.01, l1_ratio=0.5, random_state=42).fit(X_tr, y_tr)
        elif name == "knn":
            from sklearn.neighbors import KNeighborsRegressor
            m = KNeighborsRegressor(n_neighbors=10).fit(X_tr, y_tr)
        elif name == "svr":
            from sklearn.svm import SVR
            m = SVR(kernel="rbf", C=1.0).fit(X_tr, y_tr)
        elif name == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingRegressor
            m = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42).fit(X_tr, y_tr)
        else:
            return None
        preds = m.predict(X_te)
        ic, ic_p = spearmanr(preds, y_te)
        duration = (datetime.now(timezone.utc) - t1).total_seconds()
        return {"oos_ic": round(float(ic), 4), "p_value": round(float(ic_p), 4), "time_s": round(duration, 3)}
    except ImportError:
        return None
    except Exception as e:
        return {"oos_ic": None, "error": str(e)[:200]}


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
            "angle": "ml_model_pipeline",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(close) < 50:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "ml_model_pipeline",
            "status": "insufficient_data",
            "n_observations": len(close),
        }])

    returns = close.pct_change()
    features = pd.DataFrame({
        "ret_1": returns.shift(1),
        "ret_2": returns.shift(2),
        "ret_3": returns.shift(3),
        "ret_5": returns.shift(5),
        "sma_5": close.rolling(5).mean() / close - 1,
        "sma_21": close.rolling(21).mean() / close - 1,
        "vol_5": returns.rolling(5).std(),
        "vol_21": returns.rolling(21).std(),
        "high_low": (bars["high"].astype(float) - bars["low"].astype(float)) / close,
        "volume_ratio": bars["volume"].astype(float) / bars["volume"].astype(float).rolling(21).mean(),
    })

    y = returns.shift(-1)
    combined = pd.concat([features, y.rename("target")], axis=1).dropna()
    combined = combined.iloc[20:]  # skip warmup

    if len(combined) < 30:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "ml_model_pipeline",
            "status": "insufficient_data_after_features",
            "n_observations": len(combined),
        }])

    feature_cols = [c for c in features.columns]
    X = combined[feature_cols].values.astype(np.float32)
    y_vals = combined["target"].values.astype(np.float32)

    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    split = int(len(X) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y_vals[:split], y_vals[split:]

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "ml_model_pipeline",
        "metric": "data_prep",
        "n_features": len(feature_cols),
        "n_train": len(X_tr),
        "n_test": len(X_te),
    })

    if not HAS_SCIPY:
        return pd.DataFrame(rows + [{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "ml_model_pipeline",
            "metric": "error",
            "status": "scipy_not_available",
        }])

    results = {}
    for name in ["ridge", "random_forest", "xgboost", "lightgbm", "catboost",
                  "elastic_net", "knn", "svr", "gradient_boosting"]:
        r = _try_model(name, X_tr, y_tr, X_te, y_te)
        if r is not None:
            results[name] = r
            row = {
                "symbol": symbol,
                "analysis_at": analysis_at,
                "time_format": time_format,
                "angle": "ml_model_pipeline",
                "metric": "model_result",
                "model": name,
            }
            row.update(r)
            rows.append(row)

    valid = {n: r for n, r in results.items() if r.get("oos_ic") is not None}
    if valid:
        best = max(valid, key=lambda n: valid[n]["oos_ic"])
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "ml_model_pipeline",
            "metric": "best_model",
            "model": best,
            "oos_ic": valid[best]["oos_ic"],
        })
        for rank, (name, r) in enumerate(sorted(valid.items(), key=lambda x: x[1]["oos_ic"], reverse=True), 1):
            rows.append({
                "symbol": symbol,
                "analysis_at": analysis_at,
                "time_format": time_format,
                "angle": "ml_model_pipeline",
                "metric": "model_ranking",
                "rank": rank,
                "model": name,
                "oos_ic": r["oos_ic"],
            })

    return pd.DataFrame(rows)
