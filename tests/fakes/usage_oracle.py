from __future__ import annotations

from datetime import datetime

from houba.errors import UsageOracleError
from houba.ports.usage_oracle import UsageObservation, UsageQuery


class FakeUsageOraclePort:
    """Seed `last_seen` per digest; journal every query. `fail` digests raise."""

    def __init__(
        self,
        last_seen: dict[str, datetime] | None = None,
        fail: set[str] | None = None,
    ) -> None:
        self._last_seen = last_seen or {}
        self._fail = fail or set()
        self.queried: list[UsageQuery] = []

    def last_prod_usage(self, query: UsageQuery) -> UsageObservation:
        self.queried.append(query)
        if query.digest in self._fail:
            raise UsageOracleError(f"fake oracle failure for {query.digest}")
        seen = self._last_seen.get(query.digest)
        return UsageObservation(last_seen=seen, detail="seen" if seen else "not seen")
