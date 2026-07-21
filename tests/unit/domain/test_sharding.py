from __future__ import annotations

from knock.domain.sharding import owns, policy_shard


def test_policy_shard_is_deterministic() -> None:
    assert policy_shard("redis", shard_count=8) == policy_shard("redis", shard_count=8)


def test_policy_shard_in_range() -> None:
    for name in ["redis", "nginx", "boom", "a", "team/app"]:
        assert 0 <= policy_shard(name, shard_count=4) < 4


def test_policy_shard_does_not_use_builtin_hash() -> None:
    import hashlib

    expected = int.from_bytes(hashlib.sha256(b"redis").digest()[:8], "big") % 1000
    assert policy_shard("redis", shard_count=1000) == expected


def test_owns_partitions_names_exactly_once() -> None:
    names = ["redis", "nginx", "boom", "postgres", "valkey", "envoy", "etcd"]
    n = 3
    for name in names:
        owners = [i for i in range(n) if owns(name, shard_index=i, shard_count=n)]
        assert owners == [policy_shard(name, shard_count=n)]


def test_shard_count_one_owns_everything() -> None:
    for name in ["redis", "nginx", "boom"]:
        assert owns(name, shard_index=0, shard_count=1)
