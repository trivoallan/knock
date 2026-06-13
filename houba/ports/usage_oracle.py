"""Port: ask an external observability backend when a digest was last seen in prod.

The adapter OBSERVES (returns the most recent prod sighting within a window); the
pure domain DECIDES (`houba.domain.purge.decide_purge`). Keying is by digest; the
ref and 3-level identity are carried so richer adapters can match on them too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from houba.domain.lifecycle import MarkIdentity


@dataclass(frozen=True)
class UsageQuery:
    digest: str  # primary key — the sha256 the marked tag resolves to
    image_ref: str  # registry/repo:tag — corroborating
    identity: MarkIdentity  # policy / import / variant from the mark
    since: datetime  # look-back lower bound = now - minIdle


@dataclass(frozen=True)
class UsageObservation:
    last_seen: datetime | None  # most recent prod sighting in [since, now]; None ⇒ none
    detail: str  # human reason for the report ("cluster prod-eu, 3d ago")


class UsageOraclePort(Protocol):
    def last_prod_usage(self, query: UsageQuery) -> UsageObservation: ...
