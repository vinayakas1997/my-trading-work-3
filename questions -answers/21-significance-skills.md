# Significance Skills - Flags + Delivery + Audit (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `21`. Related: `17`, `20`.
Status: Workers step closed small. Code steps ready to build next, no code changed yet in this doc.

---

## How significance works today (3 patterns, good)

1. Detects 3 patterns only. File `vinu-agent/agent/significance_triage.py:2`. Large funding, repeated rejection, thesis contradiction. Actively decides, not logs only.
2. Store SQLite flags. File `significance_triage.py:77` table `significance_flags` ticker + reason + detail + resolved. `SignificanceFlagStore` create, get, mark responded. Counts total vs responded.
3. Deliver Telegram Discord + mute. File `scheduler_workers.py:302` `deliver_flag`. Targets list channels. Message format `format_flag_message`. File `significance_triage.py:262`. No token = record only, no delivery. Not error.
4. Cycle 900s significance worker. Same shape as planner worker. Fail-open on detect error, skip ticker, next cycle. Good.

---

## Gaps + knobs for significance (small)

1. No mute per pattern in UI. Flags store has resolved, no mute rule. Fix: mute `repeated_rejection` 24h after 3 muted, keep `large_funding` always alert. Small flag + UI mute button planned `17` doc step 7.
Knobs: `VINU_SIGNIFICANCE_INTERVAL_SEC=900`, `TELEGRAM_TOKEN`, `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID`, `DISCORD_TOKEN`, `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID`, `VINU_SIGNIFICANCE_MUTE_HOURS=24`.
Status: Open. Small docs + 1 mute column.

---

## How skill audit works today (good)

1. Checks skill edits. File `vinu-agent/agent/skill_audit.py:131` `check_skill_edits`. Skills root + audit store. Lists `SkillEditEntry`. Worker 3600s skill-audit loop. Same pattern as live entrypoint workers.
2. Two thesis skills content. `thesis-intake-risk-rules` disqualifiers first, `thesis-intake-strategy-definitions` shape map second. Files `teams/thesis_intake/agents/theory_reviewer/prompt.md:11`. Reviewer loads both before angles. Good order.
3. Writes never code. Thesis team excludes run tools structurally, not prompt only. File `teams/thesis_intake/TEAM.md:16`. Good guard.

---

## Gaps + knobs for skills (small)

1. Skill content version not pinned to runs. Audit logs edit, but team run does not store skill version hash. Cannot prove which rules version judged thesis. Fix: store `skill_version` hash on hypothesis + lesson. Small 1 field.
Knobs: `VINU_SKILL_AUDIT_INTERVAL_SEC=3600`, `VINU_SKILL_VERSION_PIN=true`.
Status: Open. Small.

---

## Order to build (small together)

1. Mute column + UI state. 1 file store + `17` view. Do first.
2. Skill version pin on hypothesis + lesson. 1 field + audit read. After 1 green.
3. Test: flag created delivered muted, audit detects edit pins version.

After 1-3, workers done. Next is 22 infra. Different doc.

---

## All covered proof (nothing missed for workers)

- Triage `significance_triage.py:2,77,262,270` patterns store format deliver covered.
- Workers `scheduler_workers.py:25,302,308` cycle deliver covered.
- Hook `risk_gatekeeper_hook.py:8` REJECTED row to SIG covered.
- Audit `skill_audit.py:131` covered. Skills prompts + TEAM covered.
- Channels `notify_channels.py:10` protocol covered.
- 17 UI export alerts here mute state kept. 20 lesson hypothesis evidence here skill version kept.
