"""Retention — declarative tag hygiene that feeds the soft-delete pipeline (pure).

`resolve_archive` resolves the keep/olderThanDays thresholds through the
`global ← policy` cascade (mirrors `domain.deletion_mode.resolve_deletion_mode`);
`select_retention_excess` (Task 2) picks the in-selection tags a policy keeps too
many of. No I/O, no ports — the reconcile use case bridges registry state in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from knock.domain.mirror_policy import Archive

DEFAULT_KEEP = 2
DEFAULT_OLDER_THAN_DAYS = 30


@dataclass(frozen=True)
class ResolvedRetention:
    keep: int
    older_than_days: int


def resolve_archive(policy: Archive | None, global_: Archive | None) -> ResolvedRetention | None:
    """Effective thresholds, most-specific-wins per field: policy → global → constant.

    Returns None (retention off) only when NEITHER level sets anything. Mirrors
    `resolve_deletion_mode`, but two levels (global ← policy) and per-field.
    Unlike `resolve_deletion_mode` (whose global level is always concrete and never
    returns None), here BOTH inputs are optional and a None return means retention
    is disabled.
    """
    if policy is None and global_ is None:
        return None

    keep = DEFAULT_KEEP
    for level in (policy, global_):
        if level is not None and level.keep is not None:
            keep = level.keep
            break

    older_than_days = DEFAULT_OLDER_THAN_DAYS
    for level in (policy, global_):
        if level is not None and level.older_than_days is not None:
            older_than_days = level.older_than_days
            break

    return ResolvedRetention(keep=keep, older_than_days=older_than_days)


def select_retention_excess(
    kept: dict[str, datetime],
    *,
    keep: int,
    older_than: timedelta,
    now: datetime,
    protected: frozenset[str] = frozenset(),
) -> list[str]:
    """Tags eligible for a retention mark.

    Ranked by import time descending, a tag is eligible iff
    ``(rank >= keep) AND (now - imported_at > older_than) AND tag not in protected``.
    Protected tags are excluded before ranking (always kept; `keep` applies to the
    rest). Returns the eligible tags sorted by name (deterministic).
    """
    candidates = [t for t in kept if t not in protected]
    ranked = sorted(candidates, key=lambda t: (kept[t], t), reverse=True)
    excess = [t for rank, t in enumerate(ranked) if rank >= keep and (now - kept[t]) > older_than]
    return sorted(excess)
