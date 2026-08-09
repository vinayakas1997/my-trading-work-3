"""Query/aggregation layer over walk-forward backtest result rows.

Answers questions like "what's the average hit rate during the NY session
in Q2 2024, and how many data points is that based on" — every grouped
result always carries its sample size `n`, so a thin slice never looks as
trustworthy as a well-supported one (see 05-storage-enhancement-levels/plan.md
rule 4).
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def unnest_predictions(df: pd.DataFrame, column: str = "predictions") -> pd.DataFrame:
    """Explodes a nested {horizon: {...}} dict column into one row per horizon step.

    Several angles (Chronos, Kronos, lag_llama, iTransformer, per their
    design docs) store one row per forecast with a `predictions` dict keyed
    by horizon, instead of one row per horizon step — this avoids repeating
    the same tags N times per forecast at write time. `query_slice` needs
    flat rows to group over, so this must run first for any angle using
    that shape. A no-op (returns df unchanged) for angles that already
    store flat rows.

    Dict keys are stored as strings ("1", "2", ...), not ints — pyarrow/
    parquet rejects non-str/bytes dict keys, confirmed by a real write
    attempt during Chronos's implementation. Cast back to int here (when
    the key looks numeric) so the resulting `horizon` column groups/sorts
    naturally at query time — this is invisible to callers past this
    function.
    """
    if column not in df.columns:
        return df

    other_cols = [c for c in df.columns if c != column]
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        base = {c: row[c] for c in other_cols}
        nested = row[column]
        if not isinstance(nested, dict) or not nested:
            records.append({**base, "horizon": None})
            continue
        for horizon, values in nested.items():
            rec = dict(base)
            rec["horizon"] = int(horizon) if isinstance(horizon, str) and horizon.isdigit() else horizon
            if isinstance(values, dict):
                rec.update(values)
            else:
                rec["value"] = values
            records.append(rec)
    return pd.DataFrame(records)


def query_slice(
    df: pd.DataFrame,
    group_cols: list[str],
    agg: dict[str, tuple[str, str]],
) -> pd.DataFrame:
    """Groups `df` by `group_cols` and computes `agg`, always attaching `n`.

    `agg` maps an output column name to (source_column, agg_function_name),
    e.g. {"avg_hit_rate": ("hit", "mean")} — mirrors pandas named
    aggregation. `n` (row count per group) is always included, whether or
    not the caller asked for it, so no query can silently return a rate or
    average without its sample size attached.

    Rows with a nested `predictions` column must go through
    `unnest_predictions` first — this function assumes flat rows.
    """
    if not group_cols:
        raise ValueError("group_cols must be non-empty")
    if df.empty:
        return pd.DataFrame(columns=[*group_cols, "n", *agg.keys()])

    named_aggs = {
        name: pd.NamedAgg(column=col, aggfunc=fn) for name, (col, fn) in agg.items()
    }
    grouped = df.groupby(group_cols, dropna=False).agg(
        n=(group_cols[0], "size"), **named_aggs
    )
    return grouped.reset_index()
