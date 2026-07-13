# Chapter 9 — Run Folder Layout

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/engine/engine.py` |
| **Status** | v1 |
| **Prerequisites** | ch07, ch08 |

## Path contract

`{VINU_FEATURES_DATA_DIR}/runs/{id}_{slug}/`

The numeric `id` prefix prevents title collisions.

## Delete

`DELETE /requests/{id}` or `vinu-features delete --id N` removes the folder and sets status `deleted`.
