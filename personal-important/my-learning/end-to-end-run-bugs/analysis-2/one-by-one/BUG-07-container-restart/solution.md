# BUG-07 🟠 Container Restart Loop (debug.py Not Found)

**Component:** `vinu-components`
**Files Changed:** `vinu-infra/debug.py` (moved)
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

After adding `debug.py` and rebuilding containers, the research API container entered a
restart loop with:
```
ModuleNotFoundError: No module named 'vinu_infra.debug'
```

## Root Cause

The `vinu-infra` project has a dual structure:
- Project root: `/app/vinu-infra/` (contains `pyproject.toml`, `__init__.py`)
- Package root: `/app/vinu-infra/vinu_infra/` (contains Python modules)

The `Dockerfile` does:
```dockerfile
COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra
```

The editable install (`pip install -e`) treats `/app/vinu-infra/` as the Python package
root (because of the `__init__.py` there). So modules must be at:
- `/app/vinu-infra/__init__.py` ✓
- `/app/vinu-infra/client.py` ✓
- `/app/vinu-infra/debug.py` ✓ (correct)

Not at:
- `/app/vinu-infra/vinu_infra/debug.py` ✗ (wrong — this is a nested subpackage)

The file was initially placed in the nested `vinu_infra/` directory, not at the package root.

## Suggested Fix

Move `debug.py` from `vinu_infra/vinu_infra/debug.py` to `vinu_infra/debug.py`.

## Actual Fix

```bash
cp /home/somic_cps/.../vinu-infra/vinu_infra/debug.py /home/somic_cps/.../vinu-infra/debug.py
docker compose up -d --build research-api
```

## Verification

1. `docker run --rm vinu-components-research-api:latest python3 -c "import vinu_infra.debug; print('OK')"`
2. Confirm container starts without ModuleNotFoundError
3. Run research pipeline — confirm `debug_timer` works

## Lessons Learned

- Know your package structure before adding new modules
- `pip install -e` creates editable installs — the source layout IS the package layout
- Always verify imports with `docker run --rm <image> python3 -c "import..."` before testing
- Check with `docker run --rm <image> ls -la /app/vinu-infra/__init__.py` to understand the package root
