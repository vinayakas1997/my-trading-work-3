"""Tests for recency tie-break in lead pick."""

import json

from vinu_news.analysis.enrichment.enrich import enrich_article
from vinu_news.analysis.post_enrichment.cosine_dedup.cluster import ClusterGroup
from vinu_news.analysis.post_enrichment.lead_pick.select_lead import select_leads
from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle


def test_recency_wins_on_equal_scores():
    base = {
        "headline": "Fed holds rates steady",
        "summary": "unchanged",
        "source": "REUTERS",
        "region": "US",
        "tier": 2,
        "pubDate": "Sun, 14 Jun 2026 10:00:00 GMT",
    }
    older = enrich_article({**base, "link": "https://ex.com/old"})
    newer = enrich_article({**base, "link": "https://ex.com/new", "pubDate": "Sun, 14 Jun 2026 14:00:00 GMT"})
    assert newer.article.sort_ts > older.article.sort_ts

    cluster = ClusterGroup(cluster_id="c1", members=[older, newer])
    leads = select_leads([cluster])
    assert len(leads) == 1
    assert leads[0].article.link == "https://ex.com/new"
