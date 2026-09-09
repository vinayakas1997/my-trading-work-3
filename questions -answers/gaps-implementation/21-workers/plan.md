# Plan - 21 Workers Significance Skills

Goal: Flags delivered + muted, skill version pinned.

Files touched:
- `vinu-components/vinu-agent/agent/significance_triage.py:2,77,262,270` 3 patterns store format deliver.
- `vinu-components/vinu-agent/agent/scheduler_workers.py:25,302,308` cycle deliver.
- `vinu-components/vinu-agent/agent/skill_audit.py:131` check edits.
- `teams/thesis_intake/agents/theory_reviewer/prompt.md:11`, `TEAM.md:16` 2 skills + no-run-tools guard.
- `notify_channels.py:10` protocol.

Steps:
1. Mute column + UI state (17 view).
2. Skill version hash on hypothesis + lesson.
3. Test flag delivered muted, audit pins version.

Knobs: SIGNIFICANCE_INTERVAL 900, TELEGRAM/DISCORD, MUTE_HOURS 24, SKILL_AUDIT 3600, VERSION_PIN true (see 10).
Acceptance: large funding always alerts, repeated muted 24h, version provable.
