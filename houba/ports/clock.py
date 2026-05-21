"""Port d'accès au temps. Permet de figer `now()` dans les tests."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...
