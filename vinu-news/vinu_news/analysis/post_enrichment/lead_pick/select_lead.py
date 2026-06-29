"""Select lead headline per duplicate cluster."""

from vinu_news.analysis.config.settings_loader import get_settings
from vinu_news.analysis.post_enrichment.cosine_dedup.cluster import ClusterGroup
from vinu_news.analysis.post_enrichment.lead_pick.scoring import (
    IMPACT_SCORE,
    PRIORITY_SCORE,
    SOURCE_FLAG_SCORE,
)
from vinu_news.analysis.storage.models import EnrichedArticle


def _article_score(article: EnrichedArticle) -> tuple:
    a = article.article
    score = (
        PRIORITY_SCORE.get(a.priority, 1),
        IMPACT_SCORE.get(a.impact, 1),
        SOURCE_FLAG_SCORE.get(a.source_flag, 1),
        -a.tier,
    )
    if get_settings().lead_pick.prefer_recency_tiebreak:
        return score + (a.sort_ts,)
    return score


def select_leads(clusters: list[ClusterGroup]) -> list[EnrichedArticle]:
    """Pick one lead article per cluster; mark is_lead=1."""
    leads: list[EnrichedArticle] = []
    for group in clusters:
        best = max(group.members, key=_article_score)
        best.article.is_lead = 1
        best.article.cluster_id = group.cluster_id
        leads.append(best)
    return leads
