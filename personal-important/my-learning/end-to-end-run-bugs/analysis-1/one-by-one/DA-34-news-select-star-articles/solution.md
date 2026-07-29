# DA-34 🟡 News `SELECT * FROM articles` Fetches All 23 Columns

**Component:** `vinu-news`
**Files Changed:** *(pending)*

## Problem

Multiple repository methods use `SELECT * FROM articles` when callers need only 4-5 columns. The `articles` table has 23 columns including heavy text fields (`entities_json`, `summary` up to 5KB each).

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
