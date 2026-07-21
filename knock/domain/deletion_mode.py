"""Deletion-mode cascade (pure). Resolved most-specific-wins per (policy, target):
policy → destination → global. Only the global level carries a concrete default."""

from __future__ import annotations

from enum import StrEnum


class DeletionMode(StrEnum):
    purge = "purge"  # hard-delete the tag (today's behaviour)
    mark = "mark"  # attach a pending-deletion referrer; an external reaper purges


def resolve_deletion_mode(
    policy: DeletionMode | None,
    destination: DeletionMode | None,
    global_: DeletionMode,
) -> DeletionMode:
    """Most-specific-wins. `global_` is always concrete (Settings default = purge)."""
    return policy or destination or global_
