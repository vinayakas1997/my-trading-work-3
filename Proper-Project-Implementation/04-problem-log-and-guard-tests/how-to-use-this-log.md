# How to use the problem log

The aim: an error that has been fixed once never has to be found again.

## The rules
1. **No fix without a guard.** Before changing code for a bug, write a test that fails on the old code. Fix the code. Watch the test pass. A fix without a test is logged as `FIX, NO TEST` and is the next thing to close.
2. **One entry per root cause**, not per symptom. If two symptoms have one cause, they share an entry.
3. **Every entry names its guard** as `path/to/test_file.py::test_name` (relative to `vinu-components`) so the check script can find it.
4. **Every entry lists what must agree** (other places that share the setting). This is the list that stops the same mistake in another place. The master list is the change-impact table in `02-functional-and-non-functional-requirements/requirements.md`.
5. **Never delete an entry.** When a problem is fixed, change its status. History stays.
6. **A problem found but not fixed goes in section E (open problems)** the day it is found, with the next step.
7. **A fix is not finished** until the image is rebuilt, the container recreated, the logs read, and the guard passes inside the container (`scripts/stack.sh deploy`, `scripts/test_in_containers.sh <services>`).

## The entry template
```
### P## Short name of the problem
- **Seen:** what was observed.
- **Root cause:** why it happened.
- **Fix:** what changed, and where.
- **Guard:** `path/to/test_file.py::test_name`
- **Must agree with:** the other places that share this setting.
- **Status:** GUARDED | FIX, NO TEST | PARTIAL | OPEN
```

## The check
```
python scripts/check_problem_log.py            # run from vinu-components
python scripts/check_problem_log.py --strict   # fails while any entry is not fully guarded
```
It reports the counts by status, every named test that no longer exists (renamed, moved or deleted), and every entry that is not fully guarded. Run it after every deploy and before saying a piece of work is done. It does not run the tests; it checks they are still there. Run the tests with `scripts/test_in_containers.sh`.

## Where it fits
- `00` says what the system is for. `01` shows how the parts talk. `02` says what each part must do. `03` says how it is configured. `04` (this folder) records what went wrong and what keeps it from coming back.
