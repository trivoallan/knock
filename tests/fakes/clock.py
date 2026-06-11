from __future__ import annotations

from datetime import datetime, timedelta


class FakeClock:
    """Horloge déterministe pour les tests : now() renvoie un instant fixe injecté.

    Refuse les datetime naïves — toutes les datetimes manipulées dans houba
    doivent être tz-aware pour éviter des TypeError surprenants en runtime.
    """

    def __init__(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("FakeClock requires a timezone-aware datetime")
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
