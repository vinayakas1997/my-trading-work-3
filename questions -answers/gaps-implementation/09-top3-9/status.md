# Status - 09-top3-9

Date: 2026-09-09
State: doing (diversity+writer done, regime pending)
Owner: agent build
Doing: diversity + writer done. Next regime tag + freeze + corr.
Done:
- comparison.py: _shape_of + diverse_top_n 3, best per shape, fill by score.
- research_artifact_writer.py: write_artifacts_from_top3 top3 per interval BENCHING idempotent, 4->3 cap verified.
Bugs found while implementing: none, additive no break 9 green.
Other files touched:
- vinu-components/vinu-research/vinu_research/comparison.py
- vinu-components/vinu-agent/vinu_agent/agent/research_artifact_writer.py:112
Next: freeze hash required + rehearsal cost-aware.
Done3:
- Artifact.regime_tag + store migration + writer passthrough, real DB 5 rows migrate '' verified, 60+9 green.
Done4:
- corr gate 0.85 already wired promotion_correlation_threshold, 14 green verified.
