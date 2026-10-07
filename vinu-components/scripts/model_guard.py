"""Restart the model server when it wedges (problem log O19).

The model (`hindsight-llm`, llama.cpp, one slot) sometimes freezes mid-generation: the slot stays `is_processing` with the same
task and the same `n_decoded` for good, and every call behind it times out. Its health check still says healthy. This script is
run every minute by a host scheduled task (`scripts/install_model_guard.ps1`). Each run reads `/slots`; if the slot has shown
the same task at the same token count for `STALL_AFTER_SEC`, it restarts the container, then leaves it alone for `COOLDOWN_SEC`.

    python scripts/model_guard.py            # one check (what the scheduled task runs)
    python scripts/model_guard.py --dry-run  # say what it would do, restart nothing
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "logs" / "model_guard.json"
LOGFILE = ROOT / "logs" / "model_guard.log"
SLOTS_URL = "http://127.0.0.1:8092/slots"
CONTAINER = "hindsight-llm"
STALL_AFTER_SEC = 300       # one frozen slot this long is a wedge (normal calls finish in under 200 s)
COOLDOWN_SEC = 600          # after a restart, give the model time to load before judging it again


def slot_signature(slots: list[dict]) -> tuple | None:
    """(task id, tokens decoded) of the busy slot, or None when no slot is processing."""
    for s in slots:
        if s.get("is_processing"):
            nt = s.get("next_token")
            nt = nt[0] if isinstance(nt, list) and nt else (nt or {})
            return (s.get("id_task"), nt.get("n_decoded"), s.get("n_prompt_tokens_processed"))
    return None


def decide(state: dict, signature: tuple | None, now: float) -> tuple[dict, bool]:
    """(new state, restart?). The state remembers the signature and since when it has not changed."""
    state = dict(state)
    if now < state.get("cooldown_until", 0):
        return state, False
    if signature is None:
        return {"cooldown_until": 0}, False
    sig = list(signature)
    if state.get("signature") != sig:
        return {"signature": sig, "since": now, "cooldown_until": 0}, False
    if now - state.get("since", now) >= STALL_AFTER_SEC:
        return {"cooldown_until": now + COOLDOWN_SEC}, True
    return state, False


def _log(text: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    with LOGFILE.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    try:
        slots = json.loads(urllib.request.urlopen(SLOTS_URL, timeout=10).read())
    except Exception as exc:  # noqa: BLE001 -- unreachable is not "wedged": the container may be starting or stopped
        _log(f"slots unreadable ({type(exc).__name__}); doing nothing")
        return 0
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        state = {}
    new_state, restart = decide(state, slot_signature(slots), time.time())
    if restart:
        _log(f"slot frozen for {STALL_AFTER_SEC}s ({state.get('signature')}); {'would restart' if dry else 'restarting'} {CONTAINER}")
        if not dry:
            subprocess.run(["docker", "restart", CONTAINER], capture_output=True, timeout=120, check=False)
    if not dry:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(new_state), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
