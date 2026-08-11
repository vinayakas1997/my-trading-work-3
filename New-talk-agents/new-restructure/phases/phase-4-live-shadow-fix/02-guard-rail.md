---
name: phase-4-guard-rail
status: proposed-not-built
purpose: what keeps the endpoint fix from becoming a bigger change than it needs to be, and what it must get right about incomplete data.
---

# Phase 4 -- Guard rails

**Build the endpoint generically -- don't let it assume an answer to the
open `BENCHING`-placement question.** `01-plan.md` flags a real,
unresolved question about where `BENCHING` sits relative to Phase 2/3's
`PEND`/`PENDBLOCK` states. `GET /agent/broker/performance/{artifact_id}`
itself doesn't need to know the answer -- it just returns performance data
for a given `artifact_id`, regardless of what stage that artifact is
currently in. Resolve the wiring question as its own step; don't bake an
assumption about it into the endpoint's implementation.

**Insufficient data must be distinct from a bad Sharpe, not indistinguishable
from one.** An artifact that just entered `BENCHING` hasn't accumulated
enough paper-trading fills to compute a meaningful Sharpe yet. The
endpoint must signal "not enough data" as its own explicit outcome --
never a `0` or `null` that `ShadowEvaluator` could misread as "this
strategy is actually performing at zero," which could trigger an
incorrect non-promotion (or worse, get treated as a real negative
signal) before there's been time to observe anything real.

**Unknown `artifact_id` gets a clean 404, not a 500.** `ShadowEvaluator`
will poll this endpoint for artifacts across their lifecycle, including
ones that may no longer exist by the time a poll fires (e.g. removed,
expired). The route needs to distinguish "this artifact doesn't exist" as
an expected, clean case from an actual server error.

**Degradation tolerance is a tuning parameter, not decided here.** How
close paper-trading Sharpe needs to be to backtest Sharpe before
auto-promotion fires is not pinned down by this plan -- same category as
the other not-yet-tuned thresholds (`N`, `K`, completeness tolerance)
across this whole build. Don't hardcode a number in this phase without
flagging it as provisional the same way those are.

**No network-exposure change beyond what already exists.** This is a new
route under the same `/broker/*` prefix as `/broker/halt`/`/broker/
account`, on the same `agent-api` service already bound to
`127.0.0.1` per `docker-compose.yml`. Confirm it doesn't need broader
exposure than that -- it shouldn't, since its only real caller is
`vinu-live`'s `ShadowEvaluator`, another container on the same private
network.
