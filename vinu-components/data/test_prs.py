import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/app/vinu-initial-analysis")
from vinu_initial_analysis.angles.peer_relative_strength.compute import compute, _aligned_closes

n = 300
base = np.linspace(0, 5, n)
rng = np.random.default_rng(0)
ts = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
b_aapl = 100 + base + 10 * rng.standard_normal(n).cumsum()
bars = pd.DataFrame({
    "bar_ts": [int(t.timestamp()) for t in ts],
    "open": b_aapl, "close": b_aapl, "high": b_aapl + 1, "low": b_aapl - 1,
})


class FakePC:
    def __init__(self):
        self.rng = np.random.default_rng(1)
        self.base = np.linspace(0, 5, n)

    def get_watchlist(self):
        return ["MSFT", "JNJ", "SPY"]

    def get_candles(self, sym, from_ts=None, to_ts=None, interval=None, limit=50000):
        track = {
            "MSFT": 100 + 0.9 * self.base + 10 * self.rng.standard_normal(n).cumsum(),
            "JNJ": 100 + 0.05 * self.base + 2 * self.rng.standard_normal(n).cumsum(),
            "SPY": 100 + 0.6 * self.base + 8 * self.rng.standard_normal(n).cumsum(),
        }
        # make MSFT strongly tied to AAPL so correlation should be high
        if sym == "MSFT":
            track["MSFT"] = b_aapl + 2 * self.rng.standard_normal(n).cumsum()
        close = track[sym]
        return [{"bar_ts": int(t.timestamp()), "close": c} for t, c in zip(ts, close)]


out = compute("AAPL", bars=bars, from_ts=int(ts[0].timestamp()), to_ts=int(ts[-1].timestamp()), time_format="1D", price_client=FakePC())
print("TYPE", type(out).__name__)
print("COLS", list(out.columns))
print("ROWS", len(out))
print("STATUS", out.get("status") if "status" in out.columns else "ok")
if len(out) and "status" not in out.columns:
    print(out[["date", "peer_symbol", "correlation", "relative_return_20d"]].head(12).to_string())
    for p in out["peer_symbol"].unique():
        sub = out[out["peer_symbol"] == p]
        print(p, "n=", len(sub), "corr_mean=", round(sub["correlation"].mean(), 3), "corr_range=", (round(sub["correlation"].min(),2), round(sub["correlation"].max(),2)))