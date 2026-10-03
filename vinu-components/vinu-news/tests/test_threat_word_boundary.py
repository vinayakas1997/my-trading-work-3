from vinu_news.analysis.enrichment.threat import classify_threat as c


def test_keywords_match_at_a_word_start_and_stems_still_work():
    assert c("Shares halted in a trading halt", "NEUTRAL")["threat_level"] == "CRITICAL"
    assert c("Analyst downgrades the stock", "NEUTRAL")["threat_level"] == "HIGH"
    assert c("Firm announces layoffs", "NEUTRAL")["threat_level"] == "MEDIUM"
    assert c("Tensions escalating in region", "NEUTRAL")["threat_cat"] == "conflict"


def test_a_keyword_inside_another_word_no_longer_matches():
    assert c("Patriot Brands beats estimates", "NEUTRAL")["threat_level"] == "INFO"
    assert c("Deregulation boosts banks", "NEUTRAL")["threat_level"] == "INFO"
    assert c("Apple draws attention from buyers", "NEUTRAL")["threat_level"] == "INFO"
