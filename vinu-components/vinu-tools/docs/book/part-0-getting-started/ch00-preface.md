# Chapter 0 — Preface

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Status** | v1 |
| **Prerequisites** | vinu-stock-price running |

## Learning objectives

- Understand where vinu-features sits in the Vinu pipeline (Step 3).
- Know inputs (OHLCV) and outputs (registry + parquet runs).

## Summary

vinu-features turns price candles into indicator columns using preset blueprints. Jobs are tracked in SQLite; results are written as manifest + parquet folders, not a live feature database.
