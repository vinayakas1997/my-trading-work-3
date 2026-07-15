from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseChannel(ABC):
    name: str = "base"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send_message(self, chat_id: str, text: str) -> None:
        ...

    @property
    def is_running(self) -> bool:
        return self._running
