# Features: logic checking

Phase 1 only (code and logic, no real data; see `../working-rules.md`). The routing work (`../routing-find-and-fix/`) checked that data **reaches** the next step. This folder checks that each step **does the right thing with it**, following the vision in `../vision-trding-system.md` and the how-it-is-built map in `../how-system-implemented.md`.

Each file is a set of questions and answers. Every answer has the same parts:

| Part | Meaning |
|---|---|
| **Verdict** | `WORKS` (the logic does its role, proven by a hand-worked example or test) · `WORKS, WITH A LIMIT` (does its role, but a named limit applies) · `GAP` (the vision asks for it, the code does not do it) · `FIXED` (a gap or bug found here and corrected, with a test) · `DECISION` (needs your call, options given) |
| **What I found** | the function and file, and what it really does (read in the code, not taken from a doc) |
| **Why it works / worked example** | small hand-made numbers, the answer worked out by hand, and the test that asserts it |
| **Waits for data** | what only paper trading can show (Phase 2/3). Stated, never guessed. |

| File | Question |
|---|---|
| `00-findings-and-decisions.md` | Everything found by this check: bugs fixed, gaps, decisions for you. One list. |
| `01-handling-a-loss.md` | How does the system handle a failure or a loss in a trade? |
| `02-getting-better.md` | How does the system get better and better? |
| `03-preparing-for-the-future.md` | How does it get ready for what comes next? |
| `04-finding-analogies.md` | How does it find new analogies (similar past situations, new ideas)? |
| `05-each-step-works.md` | Does each step do its role? One worked example per step on the money path. |

Rules for what counts as proof here:

* A claim is `WORKS` only when a test asserts a hand-worked number or an observable effect, and I have seen it fail when the logic is broken (mutation-checked) or the test already existed with exact numbers.
* "Mechanism verified, improvement waits for data" is the most any Phase 1 check can say about "gets better". Whether the system actually improves needs real trades.
* A function that exists but is never fed (a store nobody writes, a metric nobody reads) is **not** `WORKS`. It is a `GAP` even if its own unit tests pass. The decay finding in `00` is exactly that case.
