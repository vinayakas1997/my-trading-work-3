# Chapter 1 (Angles) — worked example, two tickers

Illustrative only — every value below is FAKE, matching the same
labeled-fake convention used throughout `angle-comprehension-hierarchy/
angle-reference/`. Never treat these numbers as real AAPL/MSFT signals.
Shows what `ask_ticker_book`'s real responses look like once built, per
`01-plan.md`'s design, for two tickers in different real states:
**AAPL** is fully comprehended (all 4 sub-chapters available), **MSFT**
has only just entered `vinu-initial-analysis` (1b available, 1c/1d not
yet — comprehension hasn't run for it).

---

## `chapter="index"` — no ticker needed, same for every caller

1a lives inside this response too (it's ticker-independent, so it's
shown once here, not repeated per ticker below).

```json
{
  "chapters": {
    "angles": {
      "title": "Angles",
      "sub_chapters": {
        "glossary": {
          "id": "1a",
          "ticker_independent": true,
          "description": "What each angle measures -- definitions, not results."
        },
        "per_ticker": {"id": "1b", "ticker_independent": false, "description": "Per-ticker angle data, every real declared timeframe."},
        "clusters": {"id": "1c", "ticker_independent": false, "description": "7-cluster synthesis."},
        "cross_cluster": {"id": "1d", "ticker_independent": false, "description": "Cross-cluster corroboration."}
      }
    },
    "experience": {
      "title": "Experience",
      "available": false,
      "reason": "not yet built, see recording-the-experiece/",
      "sub_chapters": {
        "shadow_evaluator": {"id": "2b", "status": "planned -- first focus"},
        "simulation_recorded_results": {"id": "2a", "status": "planned -- second"}
      }
    }
  },
  "cluster_index": {
    "A": {"title": "Classical statistical forecasts", "members": ["arima", "exponential_smoothing", "kalman_filters"]},
    "B": {"title": "Deep-learning / foundation-model forecasts", "members": ["chronos", "dlinear", "...", "tips_regime_aware_transformer"]},
    "C": {"title": "Volatility & drawdown risk", "members": ["garch", "drawdown_deep_dive"]},
    "D": {"title": "Regime & trend structure", "members": ["regime_analysis", "trend_lifecycle", "trend_session_structure"]},
    "E": {"title": "Shock / personality behavior", "members": ["shock_clustering", "shock_personality"]},
    "F": {"title": "Cross-asset & causality", "members": ["peer_relative_strength", "news_price_causality"]},
    "G": {"title": "Validation & attribution", "members": ["backtesting_44_metrics", "pnl_attribution"]}
  }
}
```

---

## AAPL — `chapter="angles"`, ticker="AAPL" (fully comprehended)

```json
{
  "ticker": "AAPL",
  "source_run_id": "run_20260923_0417_AAPL",
  "updated_at": "2026-09-23T04:17:00Z",

  "glossary": {
    "available": true,
    "data": {
      "arima": {"title": "ARIMA Classical Statistical Baseline", "purpose": "One-step-ahead point forecast + 95% CI.", "cluster": "A"},
      "exponential_smoothing": {"title": "Exponential Smoothing Classical Baseline", "purpose": "Holt's linear trend forecast.", "cluster": "A"},
      "kalman_filters": {"title": "Kalman Filter State Estimation", "purpose": "Filtered present-state level/trend -- NOT a forecast.", "cluster": "A"}
    }
  },

  "per_ticker": {
    "available": true,
    "data": {
      "arima": {"1D": {"row_count": 1, "forecast_price": 187.42}, "1H": {"row_count": 1, "forecast_price": 186.80}},
      "exponential_smoothing": {"1D": {"row_count": 1, "forecast_price": 188.50}, "1H": {"row_count": 1, "forecast_price": 186.95}},
      "kalman_filters": {"1D": {"row_count": 1, "filtered_level": 187.6}, "1H": {"row_count": 1, "filtered_level": 186.9}}
    }
  },

  "clusters": {
    "available": true,
    "data": {
      "A": {
        "title": "Classical statistical forecasts",
        "angles_with_data": 3,
        "synthesis": "arima and exponential_smoothing both forecast modest upside (187.4-188.5 at 1D, 186.8-187.0 at 1H); kalman_filters' filtered trend is flattening toward 1H, a present-state read not a third forecast.",
        "anomalies": []
      },
      "B": {"title": "Deep-learning / foundation-model forecasts", "angles_with_data": 11, "synthesis": "9 of 11 models with data lean up, confidence 0.55-0.70.", "anomalies": []}
    }
  },

  "cross_cluster": {
    "available": true,
    "data": {
      "consensus_checks": {"A_vs_B": "agree -- both lean up"},
      "corroborations": ["A", "B"],
      "redundant_clusters": ["E", "F"]
    }
  }
}
```

---

## MSFT — two real states, kept separate for accuracy

Checked against the actual write path before writing this section:
`TickerSummaryStore.upsert_summary()` has exactly one real caller
(`ticker_gate.py::_run_and_persist`), and it always writes
`angle_digest`, `cluster_digest`, `cross_cluster`, `cluster_anomalies`
together, from one comprehension run's output -- there's no code path
today where a FRESH write leaves `cluster_digest` empty while
`angle_digest` is populated. So the two real MSFT states are:

### State 1: never comprehended at all (the common case -- angle-coverage gate hasn't cleared)

No `TickerSummaryStore` row exists for MSFT yet. `chapter="angles"`
returns one top-level `available: false`, not four separately-empty
sub-chapters:

```json
{
  "ticker": "MSFT",
  "available": false,
  "reason": "no comprehension row for this ticker yet"
}
```

### State 2: a stale row (comprehended once, before this shape existed, or before it was refreshed since)

This is the real scenario the per-sub-chapter `available` flag actually
guards against -- a ticker whose last successful comprehension predates
`cluster_digest` existing (schema migration defaults old rows to `'{}'`),
or one that's been gate-deferred long enough that its row is old but not
literally absent. Less common than State 1, but real, and worse if
mishandled: an empty `{}` here reads as "checked, no clusters," when the
truth is "this row's clusters were never computed at all."

```json
{
  "ticker": "MSFT",
  "source_run_id": "run_20260810_1102_MSFT",
  "updated_at": "2026-08-10T11:02:00Z",

  "glossary": {
    "available": true,
    "data": {
      "arima": {"title": "ARIMA Classical Statistical Baseline", "purpose": "One-step-ahead point forecast + 95% CI.", "cluster": "A"}
    }
  },

  "per_ticker": {
    "available": true,
    "data": {
      "arima": {"1D": {"row_count": 1, "forecast_price": 412.10}}
    }
  },

  "clusters": {
    "available": false,
    "reason": "cluster_digest empty on this row -- last comprehension for this ticker predates cluster synthesis, or hasn't been refreshed since"
  },

  "cross_cluster": {
    "available": false,
    "reason": "cross_cluster empty -- depends on clusters, which is also unavailable on this row"
  }
}
```
