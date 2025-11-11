from __future__ import annotations

from typing import Protocol


class INotifier(Protocol):
    def send(self, text: str) -> bool: ...
