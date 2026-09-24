from vinu_agent.tools.angle_clusters import ANGLE_CLUSTERS
from vinu_agent.tools.book_index import CLUSTER_INDEX, cluster_title


def test_every_real_cluster_has_an_index_entry() -> None:
    """Regression guard: a cluster added to ANGLE_CLUSTERS without a
    title/use here would silently render as a bare letter again."""
    assert set(CLUSTER_INDEX) == set(ANGLE_CLUSTERS)


def test_members_match_angle_clusters_exactly() -> None:
    for letter, entry in CLUSTER_INDEX.items():
        assert entry["members"] == ANGLE_CLUSTERS[letter]


def test_every_entry_has_non_empty_title_and_use() -> None:
    for entry in CLUSTER_INDEX.values():
        assert entry["title"].strip()
        assert entry["use"].strip()


def test_cluster_title_lookup() -> None:
    assert cluster_title("A") == "Classical statistical forecasts"
    assert cluster_title(" b ") == "Deep-learning / foundation-model forecasts"
    assert cluster_title("Z") == ""
