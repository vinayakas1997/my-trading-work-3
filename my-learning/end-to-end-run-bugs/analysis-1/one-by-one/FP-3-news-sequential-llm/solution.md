# FP-3 🟡 News LLM Calls Are Sequential

**Component:** `vinu-news`
**Files Changed:** *(pending)*

## Problem

`step_news` iterates `for article in articles[:article_count]: POST /news/analyze` — each HTTP call blocks for the full LLM latency before the next starts. N articles = N sequential LLM calls.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
