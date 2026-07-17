# vinu-tools (renamed from vinu-features)

Trading factor computation toolkit — a library of 461 alpha factor formulas, 
24 TA indicators, and 11 recipe presets, accessible to both code and LLMs.

## Architecture: Three Pillars

```
Initial-Analysis      →  Static baseline, deterministic pipeline, no LLM
Research-Simulations  →  Strategy testing, LLM-driven, sandboxed
Live-Trading          →  Production deployment, real money, deterministic
```

## Directory Structure

```
vinu_tools/
├── compute/
│   ├── operators.py          ← Core math (rank, ts_corr, delta, etc.)
│   ├── registry.py           ← SINGLE unified registry (merged from 3 old files)
│   ├── alpha_meta.py         ← AlphaMeta dataclass
│   ├── alpha_factors/        ← Original Python factor files (DO NOT MOVE)
│   │   ├── academic/         ← 11 academic factors
│   │   ├── fundamental/      ← 4 fundamental factors
│   │   ├── alpha101/         ← 101 Kakushadze factors (REAL formulas)
│   │   └── gtja191/          ← 191 GTJA factors (qlib158 DELETED — duplicate)
│   ├── formulas/             ← NEW: organized factor access
│   │   ├── catalog/          ← YAML source of truth (auto-generated + hand-enriched)
│   │   │   ├── alpha101.yaml
│   │   │   ├── gtja191.yaml
│   │   │   ├── academic.yaml
│   │   │   └── fundamental.yaml
│   │   ├── compiled/         ← Original Python files (referenced by YAML)
│   │   └── engine/           ← Evalutor + expression engine + bridge
│   │       └── bridge.py     ← compute_factor() — single entry point
│   ├── meta/                 ← LLM-facing catalogs
│   │   └── concept_index.py  ← Auto-generated keyword→factor ID mapping
│   ├── bench/                ← IC bench + decay + backtest (WIRED)
│   │   ├── runner.py         ← bench_factor(), bench_factors(), bench_zoo()
│   │   ├── backtest.py       ← backtest_factor(), compare_factors()
│   │   └── decay.py          ← compute_ic(), compute_ic_decay(), estimate_half_life()
│   ├── indicators/           ← 24 TA indicator modules (unchanged)
│   ├── ml/                   ← ML models (WIRED)
│   │   ├── train.py          ← train(), train_predict(), predict()
│   │   ├── evaluate.py       ← evaluate() — IC, MSE, MAE, R2
│   │   ├── select.py         ← list_models(), select_best(), get_model()
│   │   ├── labels.py         ← create_label() — forward return labels
│   │   └── preprocess.py     ← normalize() — z-score
│   ├── bigger_recipe/        ← Recipe presets (alpha158, alpha360, etc.)
│   │   ├── alpha101_benchmark/  ← RENAMED from alpha101 (simplified formulas)
│   │   └── ...
│   ├── feature_spec.py       ← Feature spec parsing
│   ├── factor_expressions.py ← Expression engine for combining factors
│   ├── alpha_bench.py        ← IC benchmark (used by bench/runner.py)
│   ├── factor_backtest.py    ← Factor backtesting (used by bench/backtest.py)
│   └── factor_decay.py       ← Factor decay analysis (used by bench/decay.py)
├── presets/registry.py       ← BACKWARD-COMPAT STUB (re-exports from registry)
├── server/                   ← HTTP API (FastAPI)
│   ├── app.py                ← create_app() — wires routers
│   ├── routes_features.py    ← GET /factors, /factors/search, /factors/{id},
│   │                            POST /factors/{id}/bench, GET /ml/models
│   └── routes_requests.py    ← CRUD for feature requests
├── cli.py                    ← CLI entry
└── service.py                ← Feature service

scripts/
├── generate_yaml_catalog.py  ← Regenerate YAML from factor files (preserves manual edits)
└── generate_concept_index.py ← Regenerate concept index from YAML
```

## Key Changes Made

1. **qlib158 individual files DELETED** (154 files — exact duplicates of alpha158 recipe)
2. **alpha101 recipe RENAMED** to `alpha101_benchmark` (simplified template formulas, NOT real Kakushadze)
3. **Three registries MERGED** into single `registry.py` (old files are backward-compat stubs)
4. **YAML catalogs** in `formulas/catalog/` (auto-generated, manually enrichable)
5. **concept_index.py** keyword→factor ID lookup (auto-generated from YAML)
6. **compute_factor() bridge** — single entry point for LLM to compute any factor

## How To Use (LLM-facing)

### Discover factors
```python
from vinu_tools.compute.meta.concept_index import find_factors, search_factors

# Exact lookup
find_factors("volume_price_divergence")

# Fuzzy search
search_factors("find factors for short term reversal")

# Get full spec
from vinu_tools.compute.formulas.engine import resolve_factor_spec
spec = resolve_factor_spec("gtja191_001")
# → {"id": "gtja191_001", "description": "...", "params": {...}}
```

### Compute a factor (with optional param overrides)
```python
from vinu_tools.compute.formulas.engine import compute_factor, resolve_factor_spec

result = compute_factor("gtja191_001", panel)

# Override default params (validated against YAML ranges)
spec = resolve_factor_spec("gtja191_006")
# → spec["params"] = {"window": {"default": 4, "range": [2, 16]}, "lag": ...}
result = compute_factor("gtja191_006", panel, params={"window": 10, "lag": 5})
# Raises ValueError if param is out of range
```

### Bench a factor (classify as ALIVE/REVERSED/DEAD)
```python
from vinu_tools.compute.bench import bench_factor, bench_factors, bench_zoo

# Single factor
result = bench_factor("gtja191_001", panel)
# → {"status": "alive"/"reversed"/"dead", "ic_mean": 0.05, "theme": [...], ...}

# Multiple factors, ranked by |IC|
results = bench_factors(["gtja191_001", "alpha101_001"], panel)

# Entire zoo group (first 10 for speed)
results = bench_zoo("gtja191", panel, max_factors=10)
```

### Backtest a factor
```python
from vinu_tools.compute.bench import backtest_factor, compute_ic, compute_ic_decay

# Long/short backtest
bt = backtest_factor(factor_values, forward_returns, weight_scheme="equal")
bt.metrics["sharpe_ratio"]

# IC analysis
ic = compute_ic(factor_values, forward_returns)
ic_decay = compute_ic_decay(factor_values, forward_returns, max_lag=20)
half_life = estimate_half_life(ic_decay)
```

### ML models
```python
from vinu_tools.compute.ml import (
    train, train_predict, predict,
    evaluate, select_best, list_models, get_model,
    create_label, normalize,
)

# Train a model
estimator, preds = train("linear_regression", X, y)

# Train/predict with test set
train_preds, test_preds = train_predict("ridge", X_train, y_train, X_test)

# Auto-select best model from candidates
best_name, best_ic, results = select_best(X_train, y_train, X_test, y_test)

# Evaluate predictions
metrics = evaluate(y_true, y_pred)
# → {"ic": 0.31, "mse": 1.08, "mae": 0.84, "r2": 0.08}

# Create forward return labels
labels = create_label(rows, "forward_return_1")

# Normalize
normed = normalize(values)

# List available models
list_models()  # → 9 models
```

### Get registry data
```python
from vinu_tools.compute.registry import (
    get_alpha_registry, list_indicators, list_presets, expand_features
)
reg = get_alpha_registry()
reg.count()       # 307 alphas
list_indicators() # 24 indicators
list_presets()    # 11 presets
```

## Status

- All 307 factor descriptions enriched in YAML catalogs ✅
- 216 of 307 factors have tunable params in YAML catalogs — actively wired via kwargs
- Bridge validates param overrides against YAML ranges (raises ValueError if out of bounds)
- Bridge passes `**merged` to compute functions — param overrides now change the output
- `bench/` wired — `bench_factor()`, `bench_factors()`, `bench_zoo()`, backtest, IC decay
- `ml/` wired — 9 models, auto-selection, labels, normalization
- Descriptions enriched for all 307 factors (auto-generated with formula parsing; 5 hand-enriched prototypes preserved)
- Concept index regenerated with new descriptions (1145 concepts)
- CLI wired — `vinu-tools factors list/search/spec`, `vinu-tools ml models`
- Service layer wired — `list_factors()`, `search_factors()`, `get_factor_spec()`, `bench_factor()`, `list_ml_models()`, `train_ml_model()`, `select_best_ml_model()`
- Server routes wired — `GET /factors`, `GET /factors/search?q=...`, `GET /factors/{id}`, `POST /factors/{id}/bench`, `GET /ml/models`
- Param wiring: 499/499 params wired (100%), all 462 files pass syntax check

## What's Next

- Hand-enrich descriptions for important factors (current auto-generated ones are functional but lack the depth of the 5 hand-enriched prototypes)

## Server Usage

```bash
# Start the HTTP API
vinu-tools serve --host 0.0.0.0 --port 8000

# List all 307 factors
curl localhost:8000/factors

# Filter by group
curl "localhost:8000/factors?group=gtja191"

# Search by concept
curl "localhost:8000/factors/search?q=short+term+reversal"

# Get factor spec
curl localhost:8000/factors/gtja191_001

# List ML models
curl localhost:8000/ml/models
```

## CLI Usage

```bash
# List all 307 factors
vinu-tools factors list

# List factors from one group
vinu-tools factors list --group gtja191

# Search by concept
vinu-tools factors search "short term reversal"

# Get full spec for a factor
vinu-tools factors spec gtja191_001

# List ML models
vinu-tools ml models
```

## Service API (for Python/LLM clients)

```python
from vinu_tools.service import FeatureService

svc = FeatureService()

# Factor discovery
svc.list_factors()
svc.search_factors("volume divergence")
svc.get_factor_spec("gtja191_006")

# Benching
svc.bench_factor("gtja191_001", panel)
svc.bench_factors(["gtja191_001", "alpha101_001"], panel)
svc.bench_zoo("gtja191", panel, max_factors=5)

# ML
svc.list_ml_models()
svc.train_ml_model("random_forest", X, y)
svc.select_best_ml_model(X_train, y_train, X_test, y_test)
```

## Scripts

```bash
# Regenerate YAML from factor Python files (preserves manual edits)
python scripts/generate_yaml_catalog.py

# Regenerate concept index from enriched YAML
python scripts/generate_concept_index.py

# Enrich descriptions and extract params (idempotent, preserves hand-enriched factors)
python scripts/enrich_yaml_catalog.py

# Add **kwargs to compute() for factors with params listed in YAML
python scripts/wire_compute_params.py

# Replace hardcoded values with kwargs lookups (must run AFTER wire_compute_params)
python scripts/parameterize_compute_functions.py

# Bench a zoo group
python -c "from vinu_tools.compute.bench import bench_zoo; import pandas as pd, numpy as np; ..."
```
