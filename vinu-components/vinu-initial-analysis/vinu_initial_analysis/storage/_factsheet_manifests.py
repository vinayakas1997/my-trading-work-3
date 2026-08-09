"""Field manifests for the fact-sheet generator (`storage/factsheet.py`).

Each angle's manifest is a fixed, exhaustive classification of every real
column that angle's stored rows carry -- written once against that angle's
own real `02-real-scenario.md` worked example, never decided ad hoc at
generation time. `factsheet.py` checks a real run's actual DataFrame
columns against this list and fails loudly on any column no `FieldSpec`
accounts for -- see
`New-talk-/08-angles-results-template-generator/plan.md`
("comparison-by-omission" is the failure mode this guards against: quietly
choosing which fields to show is an editorial framing even with zero
adjectives in the text itself).

Only "arima" is populated so far (phase 1). Extending this to the other 29
registry entries is explicit follow-up work -- not pretended here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["mean", "count_by", "group", "tag", "identity", "nested", "storage_metadata"]


@dataclass(frozen=True)
class FieldSpec:
    """One real column, and how (or whether) a fact sheet states it.

    kind="mean": numeric field, stated as its group-wise mean via
        query.query_slice (which always attaches `n`).
    kind="count_by": categorical/status field, stated as a per-value count.
    kind="group": used as a grouping dimension for the "mean" fields above
        -- only columns an angle's own real-scenario doc already proved a
        grouping against are marked this way (reusing validated slicing,
        not inventing new cuts here).
    kind="tag": a calendar/session tag column that exists on every row but
        isn't used as a default grouping dimension in phase 1 -- present
        and acknowledged, not silently dropped.
    kind="identity": a per-step identifier (e.g. bar_ts, step_index), not
        aggregate-worthy.
    kind="nested": a structured (dict/list) column not yet flattened by
        this generator -- an explicit phase-1 limitation, not a silent gap.
    kind="storage_metadata": one of `AngleStorage.write()`'s auto-stamped
        columns (symbol/angle_name/run_id/...) -- already stated once in
        the fact sheet's "Run" section, so not repeated per-row.
    """

    name: str
    column: str
    kind: Kind
    note: str | None = None


FIELD_MANIFESTS: dict[str, list[FieldSpec]] = {
    "arima": [
        FieldSpec("bar_ts", "bar_ts", "identity"),
        FieldSpec("step_index", "step_index", "identity"),
        FieldSpec("session", "session", "tag"),
        FieldSpec("subsession", "subsession", "tag"),
        FieldSpec("day_of_week", "day_of_week", "group"),
        FieldSpec("week_of_month", "week_of_month", "tag"),
        FieldSpec("month", "month", "tag"),
        FieldSpec("quarter", "quarter", "tag"),
        FieldSpec("timeframe", "timeframe", "tag"),
        FieldSpec("status", "status", "count_by", "step outcome, e.g. 'ok' or 'fit_failed'"),
        FieldSpec("n_observations", "n_observations", "mean", "number of historical bars the model was fit on for this step"),
        FieldSpec("order", "order", "nested", "the (p, d, q) ARIMA order chosen at this step"),
        FieldSpec("aic", "aic", "mean", "Akaike information criterion of the fitted model at this step"),
        FieldSpec("forecast", "forecast", "mean", "the model's point forecast for the next close"),
        FieldSpec("confidence_interval", "confidence_interval", "nested", "the forecast's [lower, upper] interval"),
        FieldSpec("confidence_level", "confidence_level", "mean", "the confidence level the interval was built at"),
        FieldSpec("actual_price", "actual_price", "mean", "the real next close the forecast is checked against"),
        FieldSpec("hit_rate", "hit", "mean", "fraction of steps where the real next close landed inside that step's own 95% confidence interval -- not a direction guess"),
        FieldSpec("abs_error", "abs_error", "mean", "absolute difference between forecast and actual_price"),
        FieldSpec("squared_error", "squared_error", "mean", "squared difference between forecast and actual_price"),
        FieldSpec("symbol", "symbol", "storage_metadata"),
        FieldSpec("angle_name", "angle_name", "storage_metadata"),
        FieldSpec("run_id", "run_id", "storage_metadata"),
        FieldSpec("started_at", "started_at", "storage_metadata"),
        FieldSpec("analysis_from", "analysis_from", "storage_metadata"),
        FieldSpec("analysis_until", "analysis_until", "storage_metadata"),
        FieldSpec("stored_at", "stored_at", "storage_metadata"),
    ],
}

# Fixed-vocabulary guard: a generated fact sheet may only ever interpolate
# {field, value, n, timestamp} into a fixed sentence template -- no code
# path chooses a *word* based on a value, so nothing here should ever
# match. This check runs over the fully rendered text (including any raw
# string field values pulled from real data, e.g. a `status` value), not
# just the template, so it also catches judgment language arriving through
# the data itself.
# Deliberately narrower than an early draft: "good"/"bad"/"best"/"worst"/
# "outperform(s)"/"underperform(s)" were removed after a real batch run hit
# them legitimately -- "best_lag_minutes"/"best_lag_correlation" are real
# field names in news_price_causality's own output (argmax over a lag
# search, the same category of term as ARIMA's own AIC grid search), and
# peer_relative_strength's whole methodology is quantifying whether one
# stock's return exceeds a peer's, which legitimately needs
# "outperform"/"underperform" as real classification terms, not editorial
# commentary. Kept: words with no plausible legitimate use as a field name
# or technical term -- these would only ever appear if something (this
# generator, or a raw data value) were actually rendering an opinion.
BANNED_WORDS: list[str] = [
    "weak", "strong", "better", "worse",
    "improve", "improved", "improving", "improvement",
    "decline", "declined", "declining",
    "beat", "beats", "beaten",
    "impressive", "poor", "excellent", "disappointing", "solid", "robust",
    "reliable", "unreliable", "trustworthy", "promising", "concerning",
    "should", "recommend", "recommended", "recommendation", "suggests",
]
