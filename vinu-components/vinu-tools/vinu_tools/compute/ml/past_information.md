# ML — Structure History

## 2026-07-17: Reorganized

### What moved
- `compute/ml_models/` → `ml/models/`

### Why
- All ML code in one place: interface layer (train, evaluate, select) + model implementations (models/)
- Clear separation of concerns

### Old directories (deleted)
- `compute/ml_models/`

### How to add a new model
1. Create `ml/models/my_model/my_model.py` (with NAME, ALIASES, create(), score())
2. Add to `ml/models/registry.py` import list
3. It's now available via `list_models()` and `train("my_model", X, y)`
