from __future__ import annotations

from typing import Any

from houba.errors import AdapterError


class FakeNotifierPort:
    def __init__(self, *, fail: bool = False) -> None:
        self.payloads: list[dict[str, Any]] = []
        self._fail = fail

    def send(self, payload: dict[str, Any]) -> None:
        if self._fail:
            raise AdapterError("fake notifier configured to fail")
        self.payloads.append(payload)
