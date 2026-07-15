import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Attempt, Message, Session


class SessionStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, session: Session) -> Session:
        session_dir = self.base_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "attempts").mkdir(exist_ok=True)
        self._write_json(session_dir / "session.json", session.to_dict())
        return session

    def update_session(self, session: Session) -> None:
        session_dir = self.base_dir / session.session_id
        self._write_json(session_dir / "session.json", session.to_dict())

    def get_session(self, session_id: str) -> Optional[Session]:
        path = self.base_dir / session_id / "session.json"
        if not path.exists():
            return None
        return Session.from_dict(self._read_json(path))

    def list_sessions(self, limit: int = 50) -> List[Session]:
        sessions = []
        for d in self.base_dir.iterdir():
            if not d.is_dir():
                continue
            session_file = d / "session.json"
            if session_file.exists():
                sessions.append(Session.from_dict(self._read_json(session_file)))
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        session_dir = self.base_dir / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
            return True
        return False

    def append_message(self, session_id: str, message: Message) -> None:
        jsonl_path = self.base_dir / session_id / "messages.jsonl"
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(message.to_dict(), default=str) + "\n")
            os.fsync(f.fileno())

    def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        jsonl_path = self.base_dir / session_id / "messages.jsonl"
        if not jsonl_path.exists():
            return []
        messages = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(Message.from_dict(json.loads(line)))
        return messages[-limit:]

    def save_attempt(self, session_id: str, attempt: Attempt) -> None:
        attempt_dir = (
            self.base_dir / session_id / "attempts" / attempt.attempt_id
        )
        attempt_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(attempt_dir / "attempt.json", attempt.to_dict())

    def get_attempt(self, session_id: str, attempt_id: str) -> Attempt:
        path = (
            self.base_dir / session_id / "attempts" / attempt_id / "attempt.json"
        )
        return Attempt.from_dict(self._read_json(path))

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        os.replace(str(tmp), str(path))

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text())
