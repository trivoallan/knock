"""Pure decision for `houba gc`: which superseded scan referrers to collect.

Groups a subject's scan-result referrers by (tool, format) and, within each
group, applies the keep-N + older-than retention model from domain.retention.
Fail-safe: any referrer whose scan timestamp cannot be parsed is ignored
(never collected) — we only delete what we understand. No I/O, no config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from houba.domain.retention import select_retention_excess
from houba.ports.registry import Referrer


@dataclass(frozen=True)
class _ParsedReferrer:
    digest: str
    tool: str
    format: str
    timestamp: datetime


def _parse(referrer: Referrer, *, prefix: str) -> _ParsedReferrer | None:
    if not prefix:
        return None
    ann = referrer.annotations
    raw = ann.get(f"{prefix}.scan.timestamp")
    if raw is None:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _ParsedReferrer(
        digest=referrer.digest,
        tool=ann.get(f"{prefix}.scan.tool", ""),
        format=ann.get(f"{prefix}.scan.format", ""),
        timestamp=ts,
    )


def select_superseded_referrers(
    referrers: list[Referrer],
    *,
    keep: int,
    older_than: timedelta,
    now: datetime,
    prefix: str,
) -> list[str]:
    """Referrer digests to collect: superseded scan results, per (tool, format).

    Keep the `keep` newest per group AND only collect those older than
    `older_than`. Unparseable referrers are ignored. Returns sorted digests.
    """
    groups: dict[tuple[str, str], dict[str, datetime]] = {}
    for ref in referrers:
        parsed = _parse(ref, prefix=prefix)
        if parsed is None:
            continue
        groups.setdefault((parsed.tool, parsed.format), {})[parsed.digest] = parsed.timestamp

    collected: list[str] = []
    for kept in groups.values():
        collected.extend(select_retention_excess(kept, keep=keep, older_than=older_than, now=now))
    return sorted(collected)
