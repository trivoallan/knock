"""Compute the reconcile plan for an expanded import against a destination's
mirror state (spec §8). Pure: source and mirror state are inputs.

Change detection is provenance-based: a transformed image's mirror digest differs
from its source, so we compare the mirror's recorded `base.digest` (the source
digest at build time) against the current source digest — not mirror vs source.
For multi-arch, the source digest is the index digest. The 7-day stability window
defers updates while a moving source digest settles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

DEFAULT_GRACE = timedelta(days=7)


@dataclass(frozen=True)
class SourceArtifact:
    digest: str  # current source digest (index digest for multi-arch)
    pushed_at: datetime


@dataclass(frozen=True)
class MirrorArtifact:
    base_digest: str  # recorded org.opencontainers.image.base.digest


def _classify(
    source: SourceArtifact,
    mirror: MirrorArtifact | None,
    now: datetime,
    grace: timedelta,
) -> Literal["import", "update", "skip"]:
    if mirror is None:
        return "import"
    if mirror.base_digest == source.digest:
        return "skip"
    if now - source.pushed_at < grace:
        return "skip"  # source moved too recently — let it settle
    return "update"
