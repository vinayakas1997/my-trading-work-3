# 06-data-audit

Question this folder answers, for every kind of data the system makes: **what is made, where it is kept, in what shape, who reads it, and is it used well?** It also notes data that is thrown away but should be kept.

## How a component file is laid out

One file per component (`news.md` first). Each data item has one card with these lines:

- **Producer:** function and what triggers it (cadence or event).
- **Store:** database and table, or file.
- **Format:** columns, and a real example taken from the running stack.
- **Access:** the route that serves it.
- **Consumers:** each reader by name, which fields it uses, what it feeds.
- **Why it exists:** one line.
- **Properties:** size now, freshness, money-mode tag.
- **Verdict:** `used well`, `single use`, `no reader`, `computed then dropped`, or `wrong shape` (the reader asks for something the producer does not send).

Findings are numbered `DA-<component letter><n>` in `findings.md` and each one is either fixed (with a problem-log entry and a guard test) or left open with the reason.

## How the facts were gathered (so you can trust or repeat them)

- Row counts and examples: read through `scripts/stack_db.py` from inside the running container, not from the host.
- Routes: read from the service's route files.
- Consumers: found by searching every other service's code for the route, the table and the client. A search finds callers in code; it does not prove a call happens at run time, so the cards say "found in code".
- Response shape: checked once by a real call from inside the agent container.

## Status

| Component | File | Status |
|---|---|---|
| news | `news.md` | DONE 2026-10-08 (pilot) |
| stock-price | `stock-price.md` | DONE 2026-10-08 |
| screener | `screener.md` | DONE 2026-10-08 |
| initial-analysis | `initial-analysis.md` | DONE 2026-10-08 |
| research | `research.md` | DONE 2026-10-08 |
| simulator and strategy | `simulator-and-strategy.md` | DONE 2026-10-08 |
| portfolio | `portfolio.md` | DONE 2026-10-08 |
| live | `live.md` | DONE 2026-10-08 |
| agent | `agent.md` | DONE 2026-10-08 |

`findings.md` is the running list across components.
