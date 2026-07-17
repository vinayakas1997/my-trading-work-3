# Factors — Structure History

## 2026-07-17: Reorganized

### What moved
- `compute/alpha_factors/` → `factors/singles/`
- `compute/bigger_recipe/` → `factors/recipes/`
- `compute/factor_expressions.py` → `factors/expressions.py`

### Why
- Single entry point for all factor-related code
- Clear separation between individual formula factors (singles) and bundled recipe presets (recipes)
- Easy to add new factors — just create a file in `singles/` or `recipes/`

### Old directories (deleted)
- `compute/alpha_factors/`
- `compute/bigger_recipe/`

### How to add a new single factor
1. Create `factors/singles/<group>/my_alpha.py`
2. Run `scripts/generate_yaml_catalog.py`
3. Run `scripts/generate_concept_index.py`

### How to add a new recipe bundle
1. Create `factors/recipes/my_bundle/my_bundle.py`
2. Add to `factors/recipes/catalog.py`
3. Run `scripts/generate_concept_index.py`
