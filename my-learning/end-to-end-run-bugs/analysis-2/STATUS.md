# Analysis-2 Status

**Fixed: 7 / 8 | Pending: 1**

| ID | Title | Severity | Status | Date Fixed | Notes |
|----|-------|----------|--------|------------|-------|
| BUG-01 | NaN in JSON responses | 🔴 CRITICAL | ✅ Fixed | 2026-07-23 | Monkey-patch in server.py |
| BUG-02 | alpha158 indicator rejected | 🟠 HIGH | ✅ Fixed | 2026-07-23 | Default recipe changed to sma/sma/rsi |
| BUG-03 | Strategy code duplicate params | 🟡 MEDIUM | ✅ Fixed | 2026-07-23 | dict.fromkeys dedup in generator.py |
| BUG-04 | LLM URL uses localhost in Docker | 🔴 CRITICAL | ✅ Fixed | 2026-07-23 | Changed to host.docker.internal |
| BUG-05 | Simulator exec() fails on LLM code | 🔴 CRITICAL | ✅ Fixed | 2026-07-23 | Import prepending before exec() |
| BUG-06 | VINU_DEBUG timing instrumentation | 🔵 LOW | ✅ Fixed | 2026-07-23 | debug.py with debug_timer/sync_timer |
| BUG-07 | Container restart loop (debug.py) | 🟠 HIGH | ✅ Fixed | 2026-07-23 | Moved file to package root |
| BUG-08 | LLM ReadTimeout on refinement prompts | 🟠 HIGH | 🔍 Root Cause Found | - | Prompt too large (5,500 chars) |

## Root Causes Overview

| Bug | Root Cause |
|-----|-----------|
| BUG-01 | `json.dumps` fails on NaN values in response data |
| BUG-02 | Default recipe="pipeline" didn't include technical indicators |
| BUG-03 | LLM generates same param in __init__ when refining code |
| BUG-04 | `.env` used `localhost` which doesn't resolve inside Docker containers |
| BUG-05 | LLM generates code without imports; `exec()` needs them in namespace |
| BUG-06 | No instrumentation existed to trace timing across pipeline |
| BUG-07 | `debug.py` placed in nested `vinu_lib/` dir, not package root |
| BUG-08 | Refinement prompt includes full prev code (3,500 chars), 7x generation prompt size |
