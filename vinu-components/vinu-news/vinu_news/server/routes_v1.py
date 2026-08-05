"""The redesigned positional API — /v1/stage1/vinu-news/{action}/{ticker}/{granularity}/{time-range}/{method}[/{run-id}]

Full spec: New-talk-/Final-implementation/03-actual-plan-findings/02-api-design.md

Correction to that spec, made here: it originally said "vinu-news doesn't
need a method selector" — written before the later decision (see
../../New-talk-/Final-implementation/03-actual-plan-findings/05-angle-reconciliation.md
and 01-method-separation.md Section 1) to build the 9 news-only methods
INSIDE vinu-news rather than vinu-initial-analysis. Now that vinu-news
hosts multiple distinct methods, {method} is required here too, mirroring
vinu-initial-analysis's shape.

This is additive, alongside the existing /news/* routes (routes_read.py,
routes_config.py) — those aren't removed.

Design notes specific to this component:
  - These 9 methods (see analysis/methods/) are lightweight — rule-based,
    lexicon, or plain TF-IDF, no heavy models — and are explicitly
    "live-feed compatible" per 01-method-separation.md: they can run the
    moment articles are available, with no separate scheduled/triggered
    distinction the way vinu-initial-analysis's expensive angle runs need.
    So `fetch` here is a **synchronous** compute-on-demand over whatever
    articles are already stored for the ticker/time-range — not a
    stored-then-polled run. There is no {run-id} polling path for this
    component; `trigger` (below) is for fetching fresh articles, not for
    kicking off a method computation.
  - `trigger` maps onto the existing ingest pipeline (`service.ingest_...`
    equivalents already exposed at /news/ingest/trigger) — it fetches new
    articles for a ticker, it does not run a method. `fetch` (with
    {method}) always runs against whatever's already stored.
  - `tier` is always "tier1" — same reasoning as vinu-stock-price's
    routes_v1.py: these are live-feed methods with no tier2/tier3
    scheduled-vs-triggered distinction, "tier1" is the closest fit
    (computed live off raw stored data, not a frozen quarterly artifact).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from vinu_news.analysis.methods.event_type_classification import classify_event_type
from vinu_news.analysis.methods.llm_sentiment_classifier_alternatives import classify_non_llm
from vinu_news.analysis.methods.multi_source_triangulation import find_triangulated_stories
from vinu_news.analysis.methods.named_entity_recognition import aggregate_top_entities, extract_entities_full
from vinu_news.analysis.methods.news_embedding_regime_detection import detect_regime_shift
from vinu_news.analysis.methods.structured_event_tuple_embeddings import extract_event_tuple
from vinu_news.analysis.methods.tfidf_semantic_clustering import cluster_semantic
from vinu_news.analysis.methods.vader_finance_tuned_sentiment import score_vader_finance
from vinu_news.analysis.methods.velocity_spike_anomaly_detection import bucket_hourly_counts, detect_velocity_spike
from vinu_news.service import NewsService

router = APIRouter(tags=["v1-stage1"])

_GRANULARITY_MAP: dict[str, str] = {
    "1min": 60, "5min": 300, "15min": 900, "1hr": 3600, "4hr": 14400, "1day": 86400,
}


def get_service() -> NewsService:
    raise RuntimeError("NewsService dependency not configured")


class Envelope(BaseModel):
    run_id: str | None
    status: str
    computed_at: str | None
    tier: str
    data: Any


def _text(article: dict) -> str:
    return f"{article.get('headline', '')} {article.get('summary', '')}".strip()


def _run_event_type_classification(articles: list[dict]) -> Any:
    return [
        {"id": a.get("id"), "event_type": classify_event_type(a.get("headline", ""), a.get("summary", ""))}
        for a in articles
    ]


def _run_named_entity_recognition(articles: list[dict]) -> Any:
    per_article = [
        {"id": a.get("id"), **extract_entities_full(a.get("headline", ""), a.get("summary", ""))}
        for a in articles
    ]
    aggregated = aggregate_top_entities([{k: v for k, v in row.items() if k != "id"} for row in per_article])
    return {"per_article": per_article, "top_entities": aggregated}


def _run_velocity_spike_anomaly_detection(articles: list[dict]) -> Any:
    items = [{"category": a.get("category", "OTHER"), "sort_ts": a["sort_ts"]} for a in articles if a.get("sort_ts")]
    buckets = bucket_hourly_counts(items)
    result: dict[str, Any] = {}
    for group, hours in buckets.items():
        ordered = sorted(hours.items())
        if len(ordered) < 2:
            result[group] = {"velocity_spike": False, "severity": None, "ratio": 0.0, "note": "not enough hourly buckets in this window"}
            continue
        recent_count = ordered[-1][1]
        older_count = ordered[-2][1]
        result[group] = detect_velocity_spike(recent_count, older_count)
    return result


def _run_multi_source_triangulation(articles: list[dict]) -> Any:
    return find_triangulated_stories(articles)


def _run_tfidf_semantic_clustering(articles: list[dict]) -> Any:
    return cluster_semantic(articles)


def _run_vader_finance_tuned_sentiment(articles: list[dict]) -> Any:
    return [{"id": a.get("id"), **score_vader_finance(_text(a))} for a in articles]


def _run_llm_sentiment_classifier_alternatives(articles: list[dict]) -> Any:
    return [{"id": a.get("id"), **classify_non_llm(_text(a))} for a in articles]


def _run_structured_event_tuple_embeddings(articles: list[dict]) -> Any:
    return [
        {"id": a.get("id"), **extract_event_tuple(a.get("headline", ""), a.get("summary", ""))}
        for a in articles
    ]


def _run_news_embedding_regime_detection(articles: list[dict]) -> Any:
    dated = sorted((a for a in articles if a.get("sort_ts")), key=lambda a: a["sort_ts"])
    if not dated:
        return {"regime_shift": False, "note": "no timestamped articles in this window"}
    n_buckets = min(4, max(2, len(dated) // 5)) if len(dated) >= 4 else 2
    bucket_size = max(1, len(dated) // n_buckets)
    buckets: list[list[str]] = []
    for i in range(0, len(dated), bucket_size):
        chunk = dated[i : i + bucket_size]
        if chunk:
            buckets.append([_text(a) for a in chunk])
    return detect_regime_shift(buckets)


_METHOD_DISPATCH: dict[str, Callable[[list[dict]], Any]] = {
    "event-type-classification": _run_event_type_classification,
    "named-entity-recognition": _run_named_entity_recognition,
    "velocity-spike-anomaly-detection": _run_velocity_spike_anomaly_detection,
    "multi-source-triangulation": _run_multi_source_triangulation,
    "tfidf-semantic-clustering": _run_tfidf_semantic_clustering,
    "vader-finance-tuned-sentiment": _run_vader_finance_tuned_sentiment,
    "llm-sentiment-classifier-alternatives": _run_llm_sentiment_classifier_alternatives,
    "structured-event-tuple-embeddings": _run_structured_event_tuple_embeddings,
    "news-embedding-regime-detection": _run_news_embedding_regime_detection,
}


def _parse_time_range(raw: str) -> tuple[int, int]:
    parts = raw.split("_")
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="time-range must be '{start-iso}_{end-iso}'")
    try:
        start = datetime.fromisoformat(parts[0])
        end = datetime.fromisoformat(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid time-range timestamps: {exc}") from exc
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


@router.get("/fetch/{ticker}/{granularity}/{time_range}/{method}", response_model=Envelope)
def fetch(
    response: Response,
    ticker: str,
    granularity: str,
    time_range: str,
    method: str,
    limit: int = Query(default=500, ge=1, le=500),
) -> Envelope:
    if granularity.strip().lower() not in _GRANULARITY_MAP:
        raise HTTPException(status_code=422, detail=f"Unsupported granularity '{granularity}'")
    handler = _METHOD_DISPATCH.get(method)
    if handler is None:
        raise HTTPException(status_code=422, detail=f"Unknown method '{method}'. Supported: {sorted(_METHOD_DISPATCH)}")

    start_ts, end_ts = _parse_time_range(time_range)
    service = get_service()
    # NewsService.get_ticker_news() also does cross-service price-reaction
    # enrichment (an HTTP call to vinu-stock-price) that none of these 9
    # text-only methods need — and which would make every fetch here
    # depend on vinu-stock-price being up, defeating the point of these
    # being fast, standalone, live-feed-compatible methods. Go straight to
    # the storage layer instead, same underlying query get_ticker_news()
    # itself delegates to before enrichment.
    articles = service._storage.get_news_for_ticker(ticker.upper(), start_ts, end_ts, limit)

    if not articles:
        response.status_code = 404
        return Envelope(run_id=None, status="not_found", computed_at=None, tier="tier1", data=None)

    result = handler(articles)
    return Envelope(
        run_id=None,
        status="ok",
        computed_at=datetime.now(timezone.utc).isoformat(),
        tier="tier1",
        data=result,
    )


@router.post("/trigger/{ticker}/{granularity}/{time_range}", response_model=Envelope, status_code=202)
def trigger(ticker: str, granularity: str, time_range: str) -> Envelope:
    """Kick off fresh ingestion covering `ticker`.

    Known scope limitation, not silently glossed over: this component's
    existing ingest pipeline (`NewsService.run_ticker_news_ingest`, also
    used by the pre-existing `/news/ingest/ticker-news` route) is
    watchlist-wide, not addressable per single ticker — there is no
    existing per-ticker ingest primitive to call into. This trigger
    validates `ticker`/`granularity`/`time-range` per the API shape and
    refreshes the whole watchlist (which must include `ticker` for this
    call to actually produce new articles for it). A true per-ticker
    ingest would need a lower-level change to the ingestion pipeline,
    out of scope for this API-layer pass.
    """
    if granularity.strip().lower() not in _GRANULARITY_MAP:
        raise HTTPException(status_code=422, detail=f"Unsupported granularity '{granularity}'")
    start_ts, end_ts = _parse_time_range(time_range)
    days = max(1, (end_ts - start_ts) // 86400)
    service = get_service()
    run_id = uuid.uuid4().hex[:12]

    def _run() -> None:
        try:
            service.run_ticker_news_ingest(days=days)
        except Exception:
            pass  # best-effort background ingest; no job-status tracking for this component yet

    threading.Thread(target=_run, daemon=True).start()
    return Envelope(run_id=run_id, status="computing", computed_at=None, tier="tier1", data=None)
