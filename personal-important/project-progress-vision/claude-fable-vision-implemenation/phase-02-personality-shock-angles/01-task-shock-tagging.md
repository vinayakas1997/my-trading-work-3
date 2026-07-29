# Task 1: Shock-Tagging Step

**Status:** IN PROGRESS

## Purpose

Implement the shock-tagging step that joins price data (gaps, volatility z-score spikes) with news events to produce a labeled set of "shock dates" per symbol.

## Approach

- Price gap: overnight gap > N standard deviations of daily returns
- Vol z-score spike: rolling z-score of daily range > threshold
- News cross-reference: join gap dates with nearby news events
- Output: list of shock events with date, type (gap/vol/news/combined), magnitude

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_initial_analysis/angles/shock_personality/spec.yaml` | — | Created |
| `vinu_initial_analysis/angles/shock_personality/compute.py` | — | Created |

## Verification

- [x] Shock-tagging matches manually-identified shock dates for known events
- [x] Confidence intervals reported, never bare point estimates
