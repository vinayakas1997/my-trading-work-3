# BUG-07 🟠 Container Restart Loop (debug.py Not Found)

**Component:** `vinu-components`
**Files Changed:** `vinu-lib/debug.py` (moved)
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

After adding `debug.py` and rebuilding containers, the research API container entered a
restart loop with:
```
ModuleNotFoundError: No module named 'vinu_lib.debug'
```

## Root Cause

The `vinu-lib` project has a dual structure:
- Project root: `/app/vinu-lib/` (contains `pyproject.toml`, `__init__.py`)
- Package root: `/app/vinu-lib/vinu_lib/` (contains Python modules)

The `Dockerfile` does:
```dockerfile
COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib
```

The editable install (`pip install -e`) treats `/app/vinu-lib/` as the Python package
root (because of the `__init__.py` there). So modules must be at:
- `/app/vinu-lib/__init__.py` ✓
- `/app/vinu-lib/client.py` ✓
- `/app/vinu-lib/debug.py` ✓ (correct)

Not at:
- `/app/vinu-lib/vinu_lib/debug.py` ✗ (wrong — this is a nested subpackage)

The file was initially placed in the nested `vinu_lib/` directory, not at the package root.

## Suggested Fix

Move `debug.py` from `vinu_lib/vinu_lib/debug.py` to `vinu_lib/debug.py`.

## Actual Fix

```bash
cp /home/somic_cps/.../vinu-lib/vinu_lib/debug.py /home/somic_cps/.../vinu-lib/debug.py
docker compose up -d --build research-api
```

## Verification

1. `docker run --rm vinu-components-research-api:latest python3 -c "import vinu_lib.debug; print('OK')"`
2. Confirm container starts without ModuleNotFoundError
3. Run research pipeline — confirm `debug_timer` works

## Lessons Learned

- Know your package structure before adding new modules
- `pip install -e` creates editable installs — the source layout IS the package layout
- Always verify imports with `docker run --rm <image> python3 -c "import..."` before testing
- Check with `docker run --rm <image> ls -la /app/vinu-lib/__init__.py` to understand the package root
