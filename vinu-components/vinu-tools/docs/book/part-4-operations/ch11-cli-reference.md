# Chapter 11 — CLI Reference

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/cli.py` |
| **Status** | v1 |
| **Prerequisites** | ch10 |

## Commands

| Command | Purpose |
|---------|---------|
| `vinu-features submit` | Create pending request |
| `vinu-features worker --once` | Process pending queue |
| `vinu-features worker --loop` | Poll every N seconds |
| `vinu-features status --title X` | Latest row for title |
| `vinu-features list` | Filter by status/title |
| `vinu-features delete --id N` | Remove run |
| `vinu-features presets` | List blueprints |
| `vinu-features serve` | Start HTTP API |

Global overrides: `--data-dir`, `--meta-db`.
