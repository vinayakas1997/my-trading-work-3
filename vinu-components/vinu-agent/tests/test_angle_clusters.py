"""item #11 finding #2: angle_clusters.py had zero test coverage --
`cluster_digest_validator.py` trusts this data to check an LLM's output
against real membership, so an inconsistency here (a duplicate angle
across clusters, a stale reverse-lookup) would silently corrupt that
validation."""

from __future__ import annotations

from vinu_agent.tools.angle_clusters import ALL_REAL_ANGLE_IDS, ANGLE_CLUSTERS, ANGLE_TO_CLUSTER


class TestAngleClusters:
    def test_seven_clusters_a_through_g(self) -> None:
        assert set(ANGLE_CLUSTERS.keys()) == {"A", "B", "C", "D", "E", "F", "G"}

    def test_no_angle_appears_in_more_than_one_cluster(self) -> None:
        seen: set[str] = set()
        for angles in ANGLE_CLUSTERS.values():
            for angle in angles:
                assert angle not in seen, f"{angle} appears in more than one cluster"
                seen.add(angle)

    def test_reverse_lookup_matches_the_forward_mapping(self) -> None:
        for cluster, angles in ANGLE_CLUSTERS.items():
            for angle in angles:
                assert ANGLE_TO_CLUSTER[angle] == cluster

    def test_all_real_angle_ids_matches_the_reverse_lookup_keys(self) -> None:
        assert ALL_REAL_ANGLE_IDS == frozenset(ANGLE_TO_CLUSTER.keys())

    def test_every_cluster_is_non_empty(self) -> None:
        for cluster, angles in ANGLE_CLUSTERS.items():
            assert len(angles) > 0, f"cluster {cluster} is empty"

    def test_no_duplicate_angle_within_a_single_cluster(self) -> None:
        for cluster, angles in ANGLE_CLUSTERS.items():
            assert len(angles) == len(set(angles)), f"cluster {cluster} has a duplicate"
