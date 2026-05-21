"""Port de notification (Teams webhook en prod, no-op en dry-run)."""

from __future__ import annotations

from typing import Any, Protocol


class NotifierPort(Protocol):
    def send(self, payload: dict[str, Any]) -> None: ...
