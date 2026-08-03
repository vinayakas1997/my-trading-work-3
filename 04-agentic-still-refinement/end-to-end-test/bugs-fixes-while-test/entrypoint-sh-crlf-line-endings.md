---
name: entrypoint-sh-crlf-line-endings
status: fixed
severity: blocked-every-service-with-an-entrypoint-script
---

# Bug: all 7 `entrypoint.sh` files had CRLF line endings, crashing every container that uses one

## What was wrong

The very first `docker compose up --build -d` for this run failed
immediately: `news-api` and `stock-api` crash-looped with

```
exec /app/entrypoint.sh: no such file or directory
```

The file *does* exist in the image — this is the classic symptom of a
shebang line whose interpreter path is corrupted. Confirmed with `file`:

```
vinu-news/entrypoint.sh: Bourne-Again shell script, ASCII text executable, with CRLF line terminators
```

`git config --get core.autocrlf` on this machine returns `true`, and there
was no `.gitattributes` anywhere in the repo forcing LF for shell scripts.
On checkout, git silently converted every `entrypoint.sh`'s line endings
from LF to CRLF, turning `#!/bin/bash` into `#!/bin/bash\r` — the kernel
tries to exec an interpreter literally named `/bin/bash\r`, which doesn't
exist, and reports it as the *script* not being found rather than the
interpreter.

Every service with its own `entrypoint.sh` was affected: `vinu-news`,
`vinu-stock-price`, `vinu-tools`, `vinu-initial-analysis`,
`vinu-research`, `vinu-portfolio`, `vinu-live` (confirmed via `file` on all
7). Only `vinu-strategy`, `vinu-simulator`, `vinu-agent` were unaffected —
they use `CMD`/compose `command:` directly instead of a shell entrypoint.

## Why it mattered

This isn't a one-off local mistake — it's a property of the repo plus this
machine's git config, meaning **any Windows checkout of this repo** would
hit the exact same crash-loop on the very first `docker compose up --build`,
which is literally step 1 of `end-to-end-test/01-setup-and-rebuild.md`.
Nothing downstream of `news-api`/`stock-api` could even start, since every
other service's `depends_on: condition: service_healthy` chain gates on
these two.

## What was fixed

1. Converted all 7 `entrypoint.sh` files from CRLF to LF (`sed -i
   's/\r$//'`), confirmed via `file` afterward.
2. Added `vinu-components/.gitattributes`:
   ```
   * text=auto eol=lf
   *.sh text eol=lf
   entrypoint.sh text eol=lf
   ```
   so future checkouts (on any OS, regardless of the local `core.autocrlf`
   setting) always get LF for these files — the fix persists past this one
   session instead of needing to be repeated on the next fresh clone.

## What was achieved

Every `entrypoint.sh`-based container now actually starts. Combined with
[`data-root-docker-path-mismatch.md`](data-root-docker-path-mismatch.md)
(the second bug found immediately after this one was fixed), this is what
got all 10 containers to `healthy` for the first time in this pass.
