# moment — MOMENT Multi-Task Time-Series Foundation Model (fallback proxy)

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Forecast in the spirit of MOMENT's forecasting task (method 14 of the
32-method plan). The real `momentfm` package failed to build in this
Python 3.12 environment (`pkgutil.ImpImporter` incompatibility,
confirmed via an actual install attempt) — this angle uses an
honestly-labeled statistical fallback proxy for the forecasting task
only.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Point + p10/p90 forecast for the next
  5 periods, plus `model_backend` (always "fallback_proxy"),
  `fallback_reason`, and `task_note` flagging that only the forecasting
  task is implemented.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "point_forecast": 188.2,
      "p10": 184.0, "p90": 192.4,
      "model_backend": "fallback_proxy",
      "fallback_reason": "momentfm failed to build (pkgutil.ImpImporter incompatibility, Python 3.12)",
      "task_note": "forecasting task only; MOMENT's other tasks (classification, anomaly detection) not implemented here"
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Always a "fallback_proxy" here — the real MOMENT package couldn't even
be installed in this environment. Also note: MOMENT is normally
multi-task (classification, anomaly detection, forecasting); only the
forecasting piece exists here at all, and even that isn't the real
model.* (~45 words)
