"""Stable assignment of policies to shards for horizontal scale-out.

Uses sha256 — NOT the builtin hash(), which is per-process salted
(PYTHONHASHSEED) and would make different pods disagree on ownership,
producing both gaps and double-writes. See the horizontal-sharding spec.
"""

from __future__ import annotations

import hashlib


def policy_shard(name: str, *, shard_count: int) -> int:
    """The shard index (0..shard_count-1) that owns the policy `name`."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def owns(name: str, *, shard_index: int, shard_count: int) -> bool:
    """True if this shard owns `name`. shard_count == 1 owns everything."""
    return policy_shard(name, shard_count=shard_count) == shard_index
