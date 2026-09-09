# Plan - 02 LLM 400 (done, reference)

Goal: Keep user message after compaction, no 400.

Files touched:
- `vinu-components/vinu-agent/vinu_agent/agent/loop.py:363 _call_llm guard + 449 _auto_compact keep user` - done 06:24 image 8e1c13d.

Steps:
1. Preserve next user in auto_compact.
2. Guard _call_llm no user -> dummy.
3. Rebuild agent, restart, verify NVDA 200.
4. Record in status/testing.

Knobs: none.
Acceptance: system-only still 400 at server, loop never sends system-only. NVDA 200.
