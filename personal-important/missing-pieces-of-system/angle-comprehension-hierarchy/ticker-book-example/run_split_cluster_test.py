import json
import time
import urllib.request

ENDPOINT = "http://localhost:8092/v1/chat/completions"
MODEL = "qwen3.5-9b-q4_k_m-local"

CLUSTER_NAMES = {
    "A": "Classical statistical forecasts",
    "B": "Deep-learning / foundation-model forecasts",
    "C": "Volatility & drawdown risk",
    "D": "Regime & trend structure",
    "E": "Shock / personality behavior",
    "F": "Cross-asset & causality",
    "G": "Validation & attribution",
}

CLUSTER_MEMBERS = {
    "A": ["arima", "exponential_smoothing", "kalman_filters"],
    "B": ["chronos", "dlinear", "itransformer", "kronos", "lag_llama", "lpatchtst",
          "lstm", "moirai", "moment", "patchtst", "tft", "timer_timerxl", "timesfm",
          "tips_regime_aware_transformer"],
    "C": ["garch", "drawdown_deep_dive"],
    "D": ["regime_analysis", "trend_lifecycle", "trend_session_structure"],
    "E": ["shock_clustering", "shock_personality"],
    "F": ["peer_relative_strength", "news_price_causality"],
    "G": ["backtesting_44_metrics", "pnl_attribution"],
}

with open("clean_dataset.json", encoding="utf-8") as f:
    clean = json.load(f)
with open("uneven_dataset.json", encoding="utf-8") as f:
    uneven = json.load(f)


def render_cluster_digest(dataset: dict, members: list[str]) -> str:
    lines = []
    for name in members:
        entry = dataset.get(name, {"row_count": 0, "by_time_format": {}})
        rc = entry["row_count"]
        if rc == 0:
            lines.append(f"{name}: row_count=0 (no data)")
            continue
        for tf, vals in entry["by_time_format"].items():
            if "error" in vals:
                lines.append(f"{name}.{tf}: error={vals['error']}")
                continue
            kv = ", ".join(f"{k}={v}" for k, v in vals.items())
            lines.append(f"{name}.{tf}: {kv}")
    return "\n".join(lines)


def build_system_prompt(cluster_key: str, members: list[str]) -> str:
    member_list = ", ".join(members)
    return (
        f"You are the Angle Synthesizer, reviewing ONLY Cluster {cluster_key} "
        f"({CLUSTER_NAMES[cluster_key]}) for one ticker. This cluster's ONLY real "
        f"members are: {member_list}. You have no data and no knowledge about any "
        f"other angle or cluster -- do not mention or reference any angle name "
        f"other than the ones just listed. "
        "Each angle may have data at multiple real timeframes (1min/5min/15min/1H/4H/1D "
        "and for some angles also 1W/1M/6M). "
        "Only treat an angle+timeframe as informative if it has real data -- if an "
        "angle has row_count=0 or an 'error' field, say so plainly, don't guess. "
        "Cite specific numbers from angles that do have data. Never invent a number, "
        "trend, or signal that isn't actually in the returned data, and never invent "
        "a value for a field an angle doesn't actually report. "
        "Flag anything that looks malformed (NaN-like, impossible range) or stale "
        "rather than treating it as normal. "
        "Return: (1) how many of this cluster's own angles have real data at any "
        "timeframe (out of the real total for this cluster, stated above), (2) one "
        "short synthesis sentence for this cluster noting any real cross-timeframe "
        "pattern, (3) anomalies found. Then end with a fenced ```json block: "
        f'{{"cluster": "{cluster_key}", "angles_with_data": <int>, "synthesis": "...", '
        '"anomalies": ["..."]}.'
    )


def run_dataset(dataset: dict, dataset_name: str) -> dict:
    results = {}
    for cluster_key, members in CLUSTER_MEMBERS.items():
        digest = render_cluster_digest(dataset, members)
        system_prompt = build_system_prompt(cluster_key, members)
        user_prompt = f"Ticker: AAPL\n\n=== Cluster {cluster_key} Angle Digest ===\n{digest}"
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 3000,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=200) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - start
        results[cluster_key] = {"body": body, "elapsed_sec": elapsed}
        content = body["choices"][0]["message"].get("content", "")
        safe = content.encode("ascii", errors="replace").decode("ascii")
        print(f"=== {dataset_name} / cluster {cluster_key} done in {elapsed:.1f}s ===")
        print(safe)
        print()
        with open(f"split_cluster_results_{dataset_name}.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    return results


run_dataset(clean, "clean")
run_dataset(uneven, "uneven")
print("ALL DONE")
