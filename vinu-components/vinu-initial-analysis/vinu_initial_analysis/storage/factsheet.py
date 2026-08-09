"""Deterministic (no-LLM) fact sheet generator.

One angle, one symbol, one self-contained document: a short real
description of what the angle does (from its own `spec.yaml`, via the
already-built `catalog/angles.yaml`), the real N/window condition (when
the stored rows carry one), then a market-session x time-format table of
real results -- one row per session (closed/london/ny_premarket/
ny_regular/ny_afterhours), one column per this angle's real declared time
format. A cell states bare values with their sample size, or "not
available" if that combination has no real stored run yet -- never a
comparison, ranking, or qualitative word. Every term that appears in the
table (columns, sessions, each field) is defined in the surrounding text,
so the document needs no other file to be understood. See
`New-talk-/08-angles-results-template-generator/format.md` for the agreed
shape this implements, and `plan.md` for the reasoning.

Two more real breakdown sections follow the session table, both reusing
real columns every angle's stored rows already carry rather than
computing anything new: a calendar-tag breakdown (day_of_week/
week_of_month/month/quarter, via `_render_calendar_breakdown`) and, for
angles that store a nested `predictions` dict keyed by horizon step
(Chronos/Kronos/lag_llama/moirai/moment/timer_timerxl/timesfm-shaped
output), a per-horizon-step breakdown (via `_render_horizon_breakdown` +
`query.unnest_predictions`). Both were added after a real audit found (a)
`month`/`quarter`/`week_of_month` were being silently averaged into
meaningless numbers by the generic column classifier, and (b) every one of
those 7 angles' real headline result (horizon-step accuracy decay) was
absent from their fact sheets even though it was already sitting in
storage.

Reuses what already exists rather than reinventing it: `RunLog.get_latest_run`
for "which run is current" (never file mtime), `AngleStorage.read_latest`
for the real rows, `query.query_slice` for the grouped averages (always
attaches `n`), and `catalog/angles.yaml` (built from every angle's real
`spec.yaml`) for the angle's real purpose text and declared time formats.
"""

from __future__ import annotations

import functools
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from vinu_initial_analysis.storage._factsheet_manifests import (
    BANNED_WORDS,
    FIELD_MANIFESTS,
    FieldSpec,
)
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import FIXED_COLUMNS, AngleStorage
from vinu_initial_analysis.storage.query import query_slice, unnest_predictions

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "angles.yaml"

# The 5 real session names `_market_hours.classify_session` produces, via
# the (session, subsession) pair `_tagging.tag_row` actually stores on
# every row -- fixed row labels, fixed order (never re-sorted by value, so
# row order never implies a ranking).
_ROW_ORDER = ["closed", "london", "ny_premarket", "ny_regular", "ny_afterhours"]
_ROW_LABEL_FROM_TAGS = {
    ("closed", None): "closed",
    ("london", None): "london",
    ("ny", "premarket"): "ny_premarket",
    ("ny", "markethours"): "ny_regular",
    ("ny", "afterhours"): "ny_afterhours",
}
_SESSION_UTC_RANGES = {
    "closed": "00:00-07:00 UTC",
    "london": "07:00-13:00 UTC",
    "ny_premarket": "13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)",
    "ny_regular": "13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours",
    "ny_afterhours": "20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)",
}

_API_FETCH_TEMPLATE = "/v1/stage1/vinu-initial-analysis/fetch/{symbol}/{granularity}/{{time_range}}/{angle_name}/{run_id}"
_API_FACTSHEET_TEMPLATE = "/v1/stage1/vinu-initial-analysis/factsheet/{symbol}/{angle_name}"

# Every real row also carries these calendar tags (`_tagging.tag_row`,
# applied to every walk-forward step regardless of angle) -- a second real
# breakdown axis alongside market session. `fixed_order` is used verbatim
# when given (real weekday names, in calendar order); `None` means "sort
# the real observed values ascending" (week_of_month/month/quarter have no
# fixed vocabulary the way weekday names do). Only real observed values
# ever become a row -- unlike the session table, there is no "declared"
# universe of weeks/months/quarters to pre-list as "not available", so a
# value that never occurs in the real data is simply not shown, rather than
# fabricating a row for it.
_CALENDAR_DIMENSIONS: list[tuple[str, str, list[str] | None]] = [
    ("day_of_week", "real weekday name of the bar", [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    ]),
    ("week_of_month", "1-5, which real calendar week of that month the bar falls in", None),
    ("month", "real calendar month number, 1-12", None),
    ("quarter", "real calendar quarter, 1-4", None),
]


class UnmappedColumnsError(ValueError):
    pass


class NoRunFoundError(ValueError):
    pass


class JudgmentLanguageError(ValueError):
    pass


def _assert_no_judgment(text: str) -> None:
    lowered = text.lower()
    hits = [w for w in BANNED_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)]
    if hits:
        raise JudgmentLanguageError(
            f"fact sheet text contains judgment language {hits!r} -- this generator "
            "must only ever state bare facts"
        )


@functools.lru_cache(maxsize=None)
def _load_catalog() -> dict[str, dict]:
    """Real angle metadata (title/purpose/time_formats/outputs), built from
    every angle's own real `spec.yaml` by `catalog/generate_catalog.py` --
    not re-derived or hand-typed here."""
    if not _CATALOG_PATH.is_file():
        return {}
    import yaml

    data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    return {entry["id"]: entry for entry in data.get("angles", [])}


def _auto_classify_columns(df: pd.DataFrame) -> list[FieldSpec]:
    """Angle-agnostic column classification for any angle with no hand-
    authored `FIELD_MANIFESTS` entry -- every real column always gets
    classified by a fixed, data-driven rule (never a per-angle editorial
    choice), so no column can be silently dropped."""
    stamped = set(FIXED_COLUMNS)
    specs: list[FieldSpec] = []
    for col in df.columns:
        if col in stamped:
            specs.append(FieldSpec(col, col, "storage_metadata"))
        elif col in ("bar_ts", "step_index"):
            specs.append(FieldSpec(col, col, "identity"))
        elif col in ("session", "subsession", "day_of_week", "week_of_month", "month", "quarter", "timeframe"):
            # Calendar/session tag columns -- classified as "tag", never
            # "mean". Without this explicit list, `month`/`quarter`/
            # `week_of_month` fall through to the generic numeric branch
            # below and get silently averaged (a real confirmed bug: e.g.
            # `month=7.69` was showing up in real generated fact sheets --
            # a meaningless number, not a fact). These four columns are
            # real per-row calendar tags from `_tagging.tag_row`, not
            # measurements -- they're rendered as a breakdown *dimension*
            # (see `_CALENDAR_DIMENSIONS`), never averaged.
            specs.append(FieldSpec(col, col, "tag"))
        else:
            non_null = df[col].dropna()
            if non_null.empty:
                specs.append(FieldSpec(col, col, "identity", "column is entirely null in this run"))
                continue
            sample = non_null.iloc[0]
            if isinstance(sample, (dict, list)):
                specs.append(FieldSpec(col, col, "nested"))
            elif isinstance(sample, bool) or pd.api.types.is_bool_dtype(df[col]):
                specs.append(FieldSpec(col, col, "count_by"))
            elif pd.api.types.is_numeric_dtype(df[col]) or isinstance(sample, (int, float)):
                specs.append(FieldSpec(col, col, "mean"))
            elif isinstance(sample, str) and non_null.nunique() > max(3, len(non_null) // 2):
                # Free text, not a category -- e.g. news_price_causality's
                # real `headline` column is a different real headline on
                # almost every row, not a repeated status/label like
                # "ok"/"fit_failed". A count_by breakdown of near-unique
                # values isn't a useful aggregate and, being real quoted
                # external text (news headlines), can legitimately contain
                # any real word -- excluded from the table (and therefore
                # from the judgment-language check) rather than mis-treated
                # as a low-cardinality category.
                specs.append(FieldSpec(col, col, "identity", "free text, not a repeated category"))
            else:
                specs.append(FieldSpec(col, col, "count_by"))
    return specs


def _resolve_manifest(angle_name: str, per_tf_df: dict[str, pd.DataFrame]) -> list[FieldSpec]:
    manifest = FIELD_MANIFESTS.get(angle_name)
    if manifest is not None:
        known = {s.column for s in manifest}
        for tf, df in per_tf_df.items():
            unmapped = sorted(c for c in df.columns if c not in known)
            if unmapped:
                raise UnmappedColumnsError(
                    f"{angle_name}'s real stored columns at {tf} include {unmapped!r}, "
                    f"which no FieldSpec in FIELD_MANIFESTS[{angle_name!r}] accounts for"
                )
        return manifest
    return _auto_classify_columns(next(iter(per_tf_df.values())))


def _condition_line(per_tf_df: dict[str, pd.DataFrame]) -> str | None:
    """Real N/window condition, only stated when the stored rows actually
    carry an `n_observations` column with one constant value -- never
    guessed or imported from an angle's own source code."""
    values: set[int] = set()
    for df in per_tf_df.values():
        if "n_observations" not in df.columns:
            continue
        col = pd.to_numeric(df["n_observations"], errors="coerce").dropna()
        values.update(int(v) for v in col.unique())
    if len(values) == 1:
        n = next(iter(values))
        return (
            f"Condition: N={n} candles of history considered before each forecast "
            f"(\"{n} candles\" means {n} candles at that column's own resolution -- "
            f"{n} one-minute candles for the `1min` column, {n} daily candles for the "
            "`1D` column, not a fixed time window applied to every column)."
        )
    return None


def _period_line(per_tf_df: dict[str, pd.DataFrame]) -> str | None:
    all_ts = [
        int(v) for df in per_tf_df.values() if "bar_ts" in df.columns
        for v in df["bar_ts"].dropna().tolist()
    ]
    if not all_ts:
        return None
    d_from = datetime.fromtimestamp(min(all_ts), tz=timezone.utc).date()
    d_to = datetime.fromtimestamp(max(all_ts), tz=timezone.utc).date()
    span_days = (d_to - d_from).days
    total_steps = sum(len(df) for df in per_tf_df.values())
    return (
        f"Real data covers {d_from} to {d_to} ({span_days} days), {total_steps} "
        f"real steps across {len(per_tf_df)} real time format(s)."
    )


def _market_session_column(df: pd.DataFrame) -> pd.Series:
    if "session" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)
    subsession = df["subsession"] if "subsession" in df.columns else pd.Series([None] * len(df), index=df.index)
    return pd.Series(
        [
            _ROW_LABEL_FROM_TAGS.get((s, None if pd.isna(sub) else sub))
            for s, sub in zip(df["session"], subsession)
        ],
        index=df.index,
    )


def _render_grouped_table(
    row_label_header: str,
    row_order: list[str],
    grouped_by_tf: dict[str, pd.DataFrame],
    per_tf_df: dict[str, pd.DataFrame],
    per_tf_run: dict[str, dict],
    time_formats: list[str],
    value_names: list[str],
) -> list[str]:
    """One row per `row_order` entry, one column per time format -- shared
    by the session table and every calendar-tag/horizon breakdown table
    below, so they all render real values with the same `not available` /
    `not available (n=0)` rules instead of each table inventing its own."""
    lines = [
        "| " + row_label_header + " | " + " | ".join(time_formats) + " |",
        "|---" * (len(time_formats) + 1) + "|",
    ]
    for row_label in row_order:
        cells = [str(row_label)]
        for tf in time_formats:
            if tf not in per_tf_df:
                cells.append("not available")
                continue
            grouped = grouped_by_tf.get(tf)
            if grouped is None or row_label not in grouped.index:
                cells.append("not available (n=0)")
                continue
            row = grouped.loc[row_label]
            n = int(row["n"])
            run = per_tf_run[tf]
            parts = [f"{name}={row[name]:.4g}" for name in value_names]
            parts.append(f"n={n}")
            parts.append(f"computed_at={run['stored_at']}")
            parts.append(f"run_id={run['run_id']}")
            cells.append(", ".join(parts))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _render_calendar_breakdown(
    mean_specs: list[FieldSpec],
    per_tf_df: dict[str, pd.DataFrame],
    per_tf_run: dict[str, dict],
    time_formats: list[str],
) -> list[str]:
    """A second real breakdown axis alongside market session: the same
    real per-row calendar tags every angle already carries
    (`day_of_week`/`week_of_month`/`month`/`quarter`, from
    `_tagging.tag_row`). Reuses the exact same fields already defined for
    the session table above (`mean_specs`) -- no new fields, just a
    different real grouping, same as ARIMA's own `02-real-scenario.md`
    reused its own `day_of_week` grouping rather than inventing a new
    slice."""
    if not mean_specs:
        return []
    value_names = [s.name for s in mean_specs]
    agg = {s.name: (s.column, "mean") for s in mean_specs}

    lines: list[str] = ["## Breakdown by calendar tag", ""]
    lines.append(
        "Same fields as the session table above (" + ", ".join(f"`{n}`" for n in value_names) + ", plus `n`/"
        "`computed_at`/`run_id`), grouped instead by a real calendar tag every "
        "step already carries: `day_of_week` (real weekday name of the bar), "
        "`week_of_month` (1-5, which real calendar week of that month the bar "
        "falls in), `month` (real calendar month number, 1-12), `quarter` "
        "(real calendar quarter, 1-4). Unlike the session table, only real "
        "observed values become a row here -- there is no fixed universe of "
        "weeks/months/quarters to pre-list, so a value that never occurs in "
        "this run's real data is simply absent, not shown as `not available`."
    )
    lines.append("")

    any_rendered = False
    for column, description, fixed_order in _CALENDAR_DIMENSIONS:
        observed: set = set()
        for df in per_tf_df.values():
            if column in df.columns:
                observed.update(v for v in df[column].dropna().unique().tolist())
        if not observed:
            continue
        row_order = [v for v in fixed_order if v in observed] if fixed_order else sorted(observed)

        grouped_by_tf: dict[str, pd.DataFrame] = {}
        for tf, df in per_tf_df.items():
            if column not in df.columns:
                continue
            grouped_by_tf[tf] = query_slice(df, [column], agg).set_index(column)

        any_rendered = True
        lines.append(f"### {column} ({description})")
        lines.append("")
        lines.extend(
            _render_grouped_table(column, row_order, grouped_by_tf, per_tf_df, per_tf_run, time_formats, value_names)
        )
        lines.append("")

    return lines if any_rendered else []


def _render_horizon_breakdown(
    per_tf_df: dict[str, pd.DataFrame],
    per_tf_run: dict[str, dict],
    time_formats: list[str],
) -> list[str]:
    """Several angles (Chronos, Kronos, lag_llama, moirai, moment,
    timer_timerxl, timesfm, per their real design docs) store one row per
    forecast with a nested `predictions` dict keyed by horizon step instead
    of one row per step -- `query.unnest_predictions` (built for exactly
    this) explodes it. Without this, every real number inside `predictions`
    was invisible to the fact sheet even though it's the headline result
    each of these angles' own design doc describes (horizon-step accuracy
    decay)."""
    unnested_by_tf: dict[str, pd.DataFrame] = {}
    numeric_fields: list[str] = []
    for tf, df in per_tf_df.items():
        if "predictions" not in df.columns:
            continue
        flat = unnest_predictions(df, "predictions")
        if "horizon" not in flat.columns or flat["horizon"].dropna().empty:
            continue
        unnested_by_tf[tf] = flat
        for col in flat.columns:
            if col == "horizon" or col in df.columns or col in numeric_fields:
                continue
            if pd.api.types.is_numeric_dtype(flat[col]) or isinstance(flat[col].dropna().iloc[0], (int, float, bool)):
                numeric_fields.append(col)

    if not unnested_by_tf or not numeric_fields:
        return []

    observed_horizons: set = set()
    for flat in unnested_by_tf.values():
        observed_horizons.update(v for v in flat["horizon"].dropna().unique().tolist())
    row_order = sorted(observed_horizons)

    agg = {f: (f, "mean") for f in numeric_fields}
    grouped_by_tf = {tf: query_slice(flat, ["horizon"], agg).set_index("horizon") for tf, flat in unnested_by_tf.items()}

    lines = [
        "## Breakdown by forecast horizon step",
        "",
        "This angle stores a real nested `predictions` field: one entry per "
        "horizon step ahead of the forecast origin (`horizon=1` is the "
        "nearest real step forecast, higher numbers further out). Fields "
        "below (" + ", ".join(f"`{f}`" for f in numeric_fields) + ") are each "
        "real horizon step's own mean across every real step at that "
        "horizon, plus `n` (how many real steps that mean is based on). A "
        "field that only ever holds 0/1 in the raw data (e.g. `hit`) has a "
        "mean that is a real hit rate: the fraction of real steps where it "
        "was 1.",
        "",
    ]
    lines.extend(
        _render_grouped_table("horizon", row_order, grouped_by_tf, unnested_by_tf, per_tf_run, time_formats, numeric_fields)
    )
    lines.append("")
    return lines


def generate_factsheet(
    symbol: str,
    angle_name: str,
    run_log: RunLog,
    storage: AngleStorage,
    *,
    tier: str = "tier2",
) -> str:
    """Real stored data in, one plain factual document out -- spanning
    every real time format this angle has a completed run for. Raises
    rather than silently dropping or approximating anything."""
    catalog_entry = _load_catalog().get(angle_name)
    time_formats: list[str] = catalog_entry["time_formats"] if catalog_entry else []
    if not time_formats:
        # No catalog entry, or an empty declared list -- happens for real
        # registry entries whose name doesn't match their spec.yaml folder
        # (e.g. "news_price_causality_impact"/"_aggregate" both live under
        # the single "news_price_causality" folder/catalog id). Rather than
        # require an exact name match, fall back to discovering whatever
        # real granularities RunLog actually has completed runs for under
        # this exact angle_name -- still real data, not guessed, just a
        # different real source than the declared list.
        time_formats = sorted({
            row["granularity"] for row in run_log.get_runs(symbol=symbol, angle_name=angle_name, limit=1000)
            if row["status"] == "completed" and row["tier"] == tier
        })

    per_tf_df: dict[str, pd.DataFrame] = {}
    per_tf_run: dict[str, dict] = {}
    for tf in time_formats:
        run = run_log.get_latest_run(symbol, angle_name, granularity=tf, tier=tier)
        if run is None:
            continue
        df = storage.read_latest(symbol, angle_name, granularity=tf, tier=tier)
        if df.empty:
            continue
        per_tf_df[tf] = df
        per_tf_run[tf] = run

    if not per_tf_df:
        raise NoRunFoundError(
            f"no completed run found for {symbol}/{angle_name} at any of its "
            f"declared time formats {time_formats!r}"
        )

    manifest = _resolve_manifest(angle_name, per_tf_df)
    mean_specs = [s for s in manifest if s.kind == "mean"]
    count_specs = [s for s in manifest if s.kind == "count_by"]

    title = catalog_entry.get("title", angle_name) if catalog_entry else angle_name
    # The title/purpose/output description below are quoted verbatim from
    # this angle's own real spec.yaml -- real, pre-existing methodology
    # documentation, not this generator's own interpretation of any
    # computed result. Deliberately excluded from `_assert_no_judgment`
    # (checked_lines below): a word like "reliable" describing *why a
    # model has no seasonal component* is not a claim about any result,
    # and rewriting or stripping real spec.yaml text to dodge a word
    # filter would misrepresent the actual methodology doc. Everything
    # this generator itself computes from real data -- condition, period,
    # every table cell, status counts, the footer -- still goes through
    # the full check below.
    catalog_lines: list[str] = [f"# {angle_name} ({symbol}) -- {title}", ""]
    intro = f"**{angle_name} ({symbol}):**"
    if catalog_entry and catalog_entry.get("purpose"):
        intro += f" {catalog_entry['purpose'].strip()}"
    outputs = catalog_entry.get("outputs") if catalog_entry else None
    if outputs and outputs[0].get("description"):
        intro += f" Output: {outputs[0]['description'].strip()}"
    catalog_lines.append(intro)
    catalog_lines.append("")

    lines: list[str] = []

    condition = _condition_line(per_tf_df)
    if condition:
        lines.append(condition)
        lines.append("")

    period = _period_line(per_tf_df)
    if period:
        lines.append(period)
        lines.append("")

    if mean_specs:
        field_bits = ", ".join(f"`{s.name}`" + (f" ({s.note})" if s.note else "") for s in mean_specs)
        lines.append(
            f"Table columns = candle/bar time resolution (declared time formats: "
            f"{', '.join(time_formats)}). Each cell states {field_bits}, plus `n` "
            f"(how many real steps that value is based on), or `not available` when "
            f"that (session, time format) combination has no real stored run yet."
        )
        lines.append("")
        lines.append(
            "All times below are UTC. Session row labels, as fixed UTC hour ranges "
            "(New York shifts with US daylight saving; London/closed do not):"
        )
        for row_label in _ROW_ORDER:
            lines.append(f"- `{row_label}` = {_SESSION_UTC_RANGES[row_label]}")
        lines.append("")

        value_names = [s.name for s in mean_specs]
        grouped_by_tf: dict[str, pd.DataFrame] = {}
        for tf, df in per_tf_df.items():
            work = df.copy()
            work["_market_session"] = _market_session_column(work)
            agg = {s.name: (s.column, "mean") for s in mean_specs}
            grouped_by_tf[tf] = query_slice(work, ["_market_session"], agg).set_index("_market_session")

        lines.extend(
            _render_grouped_table(
                "session", _ROW_ORDER, grouped_by_tf, per_tf_df, per_tf_run, time_formats, value_names
            )
        )
        lines.append("")

        lines.extend(_render_calendar_breakdown(mean_specs, per_tf_df, per_tf_run, time_formats))

    lines.extend(_render_horizon_breakdown(per_tf_df, per_tf_run, time_formats))

    if count_specs:
        lines.append("## Status counts by time format")
        for tf, df in per_tf_df.items():
            for spec in count_specs:
                counts = df[spec.column].value_counts(dropna=False)
                total = int(counts.sum())
                for value, n in counts.items():
                    lines.append(f"{tf}: {spec.name} = {value}: n={int(n)} (of {total})")
        lines.append("")

    example_tf, example_run = next(iter(per_tf_run.items()))
    api_path = _API_FETCH_TEMPLATE.format(
        symbol=symbol, granularity=example_tf, angle_name=angle_name, run_id=example_run["run_id"]
    )
    factsheet_api_path = _API_FACTSHEET_TEMPLATE.format(symbol=symbol, angle_name=angle_name)
    lines.append(
        f"_This exact document is also available live via `GET {factsheet_api_path}`. "
        f"For the raw underlying rows behind any cell (not just its "
        f"session/time-format average), call `GET {api_path}` (`{{time_range}}` "
        f"filled in with whatever window you need; the run_id above pins the exact "
        f"computation this table's {example_tf} numbers came from). This document "
        "states values only -- it does not compare, rank, or advise between them._"
    )

    _assert_no_judgment("\n".join(lines))
    return "\n".join(catalog_lines + lines)


def write_factsheet(
    data_root: str,
    symbol: str,
    angle_name: str,
    run_log: RunLog,
    storage: AngleStorage,
    *,
    tier: str = "tier2",
) -> Path:
    """Generates and writes one angle's fact sheet to
    `{data_root}/factsheets/{symbol}/{angle_name}.md`, overwriting any
    previous version -- this file is a readable projection of RunLog/
    AngleStorage's real data, not a source of truth, so it's always
    regenerated fresh rather than versioned/accumulated."""
    text = generate_factsheet(symbol, angle_name, run_log, storage, tier=tier)
    out_dir = Path(data_root) / "factsheets" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{angle_name}.md"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def write_summary(
    data_root: str,
    symbol: str,
    run_log: RunLog,
    storage: AngleStorage,
    *,
    angle_names: list[str] | None = None,
    tier: str = "tier2",
) -> Path:
    """Combines every angle's fact sheet for one symbol into
    `{data_root}/factsheets/{symbol}/_summary.md`, in fixed order -- never
    re-sorted by value, so order never implies a ranking. Angles with no
    real completed run yet get one plain line saying so, not fabricated
    content and not silently skipped."""
    from vinu_initial_analysis.storage.orchestration_registry import ANGLE_REGISTRY

    names = angle_names if angle_names is not None else list(ANGLE_REGISTRY)
    sections = [
        f"# Angle results summary -- {symbol}",
        "",
        "One section per angle, in a fixed order. No comparison or ranking "
        "across sections is implied by that order.",
        "",
        "---",
        "",
    ]
    for angle_name in names:
        try:
            sections.append(generate_factsheet(symbol, angle_name, run_log, storage, tier=tier))
        except NoRunFoundError:
            sections.append(f"# {angle_name} ({symbol})\n\nno completed real run found yet.")
        sections.append("")
        sections.append("---")
        sections.append("")

    text = "\n".join(sections)
    out_dir = Path(data_root) / "factsheets" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "_summary.md"
    out_path.write_text(text, encoding="utf-8")
    return out_path
