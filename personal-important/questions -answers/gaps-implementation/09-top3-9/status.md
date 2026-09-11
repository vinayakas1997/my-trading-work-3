# Status - 09-top3-9

Date: 2026-09-09
State: done (all: diversity+writer+regime+freeze+corr+rehearsal)
Owner: agent build
Doing: diversity + writer done. Next regime tag + freeze + corr.
Done:
- comparison.py: _shape_of + diverse_top_n 3, best per shape, fill by score.
- research_artifact_writer.py: write_artifacts_from_top3 top3 per interval BENCHING idempotent, 4->3 cap verified.
Bugs found while implementing: none, additive no break 9 green.
Other files touched:
- vinu-components/vinu-research/vinu_research/comparison.py
- vinu-components/vinu-agent/vinu_agent/agent/research_artifact_writer.py:112
Next: none, all closed (diversity+writer+regime+freeze+corr+rehearsal).
Done6:
- Artifact.freeze_hash config lineage + migration + writer fills, old rows '' verified, 60+9 green. (Caught own bug: helper placed inside class broke create, fixed + green.)
Done5:
- rehearsal cost-aware verified: same run_backtest + T+1 + 0.001/0.0005 costs as every backtest (tools.py:410).
Done3:
- Artifact.regime_tag + store migration + writer passthrough, real DB 5 rows migrate '' verified, 60+9 green.
Done4:
- corr gate 0.85 already wired promotion_correlation_threshold, 14 green verified.
