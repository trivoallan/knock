from __future__ import annotations

from datetime import datetime, timedelta


class FakeClock:
    """Horloge déterministe pour les tests. Refuse les datetime naïves.

    L'arithmétique de dates dans `domain/tag_filter` (délai 7 jours) mélangera
    cette horloge avec des datetimes provenant d'Harbor — tous tz-aware. Une
    valeur naïve provoquerait des TypeError surprenants en runtime.
    """

    def __init__(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("FakeClock requires a timezone-aware datetime")
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
