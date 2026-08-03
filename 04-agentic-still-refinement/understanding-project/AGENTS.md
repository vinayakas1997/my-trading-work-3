---
name: understanding-project
status: reference
purpose: three concrete "what actually happens" walkthroughs for the whole vinu-components stack, each grounded in the real trigger/scheduler code (not the intended design) — for building an accurate mental model of what's automatic vs what needs a manual curl call.
---

# Understanding This Project — Three Real Scenarios

Each file below answers one question people actually ask about this system,
with the real code path cited (`file:line`), a mermaid diagram of the
cascade, and the exact `curl` command for anything that needs a manual
trigger. These are not aspirational — every "automatic" claim here was
verified against the scheduler/loop code that actually runs it, and every
"nothing happens automatically" claim was verified by grepping for the
push/webhook/notify call that would have to exist and confirming it
doesn't.

## The one fact that explains most of the surprises below

**There is no event-driven pipeline anywhere in this stack.** Nothing
calls another service because something upstream changed. Every stage is
either (a) a fixed-interval poll loop that re-reads whatever's current
next time it wakes up, or (b) purely on-demand, only running when its own
HTTP route is hit. If you're debugging "why didn't X pick up Y," the
answer is never "the event didn't fire" — there are no events — it's
either "the poll loop hasn't woken up yet" or "nobody called the route."

## The three files

1. [`a-new-strategy-added.md`](a-new-strategy-added.md) — a research run
   gets promoted to an artifact. What `vinu-portfolio` sees automatically
   (on its next read), what `vinu-strategy` never sees at all (it's a
   completely separate concept), and what needs an explicit approve call.
2. [`b-new-ticker-added.md`](b-new-ticker-added.md) — a ticker is added to
   `data/shared/watchlist.json`. Per-service breakdown of who syncs it
   automatically on a poll loop, who re-reads it fresh every call with no
   sync needed, and who has no watchlist concept whatsoever and must be
   told the symbol explicitly on every request.
3. [`c-new-data-arrives.md`](c-new-data-arrives.md) — a new candle or news
   item lands. Confirms the two real ingestion timers that exist, and the
   (perhaps surprising) fact that storing new raw data never triggers
   anything downstream — features/initial-analysis/research all run on
   their *own* independent timers or manual triggers, never because new
   data just arrived.

## Ports and route prefixes referenced throughout

| Service | Port | Route prefix |
|---|---|---|
| vinu-news | 8080 | `/news` |
| vinu-stock-price | 8081 | `/stock` |
| vinu-tools (features) | 8082 | `/features` |
| vinu-initial-analysis | 8083 | `/analysis` |
| vinu-strategy | 8084 | `/strategy` |
| vinu-simulator | 8085 | `/simulator` |
| vinu-agent | 8086 | `/agent` |
| vinu-research | 8087 | `/research` |
| vinu-portfolio | 8090 | `/portfolio` |
| vinu-live | 8091 | (not exercised in these three scenarios) |
