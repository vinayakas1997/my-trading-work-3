# ML Models — Future Implementation Plan

## Excluded (by design)

- **MLP** — small neural net on tabular features (deferred; use sklearn/boosting first)
- **LSTM** — sequence models belong outside tabular vinu-features v1

## Planned enhancements

- Model registry DB (versioned pickles + metrics)
- Walk-forward retrain scheduler
- Hyperparameter search (Optuna)
- Cross-sectional rank features for multi-symbol runs
- Agent tool endpoints: `POST /ml/train`, `POST /ml/score`

## Dependencies

Install optional ML stack:

```bash
pip install -e ".[ml]"
```

Packages: `scikit-learn`, `lightgbm`, `xgboost`, `catboost` (CatBoost may require extra setup on Windows).

## Integration contract

1. Worker writes `features.parquet`
2. If `ml_model` set on request → `labels` module builds target column
3. Model module trains on in-memory slice (or loads cached model)
4. Worker writes `scores.parquet` beside features

## API (future)

| Endpoint | Purpose |
|----------|---------|
| POST /requests with `ml_model`, `ml_label` | Feature run + score |
| GET /requests/{id}/scores | Score artifact path |
