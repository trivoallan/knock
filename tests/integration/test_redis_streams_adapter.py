"""Integration tests for RedisStreamsAdapter (QueuePort over Redis Streams).

Uses a real Redis 8 instance (REDIS_TEST_ADDR=host:port or a local redis-server).
All scenarios mirror the original test_scan_streams.py coverage plus new invariant
and RESP3 shape assertions.
"""

import time

import pytest

from houba.adapters.redis_streams import RedisStreamsAdapter
from houba.ports.queue import Reservation

WORK = "houba:scan:work"
DEAD = "houba:scan:dead"
GROUP = "scan"

MIN_IDLE_MS = 300


def _make_adapter(redis_client, *, consumer: str = "worker-1") -> RedisStreamsAdapter:
    """Construct an adapter using the test Redis client (already flushed by the fixture)."""
    return RedisStreamsAdapter(
        redis_client,
        consumer=consumer,
        work=WORK,
        dead=DEAD,
        confirmed="houba:scan:confirmed",
        placed="houba:scan:placed",
        group=GROUP,
    )


def test_enqueue_xadds_each_ref(redis_server):
    adapter = _make_adapter(redis_server)
    adapter.enqueue(["repo@sha256:a", "repo@sha256:b"])
    assert redis_server.xlen(WORK) == 2
    msgs = redis_server.xrange(WORK)
    assert [m[1]["ref"] for m in msgs] == ["repo@sha256:a", "repo@sha256:b"]


def test_enqueue_records_placed_set(redis_server):
    adapter = _make_adapter(redis_server)
    adapter.enqueue(["repo@sha256:a", "repo@sha256:b"])
    assert redis_server.smembers("houba:scan:placed") == {"sha256:a", "sha256:b"}


def test_reserve_returns_reservation(redis_server):
    adapter = _make_adapter(redis_server)
    adapter.enqueue(["repo@sha256:a"])
    res = adapter.reserve(block_ms=100)
    assert res is not None
    assert isinstance(res, Reservation)
    assert res.ref == "repo@sha256:a"
    assert res.token  # opaque stream msg_id, non-empty string


def test_reserve_then_ack_confirms_and_trims(redis_server):
    adapter = _make_adapter(redis_server)
    adapter.enqueue(["repo@sha256:a"])
    res = adapter.reserve(block_ms=100)
    assert res is not None
    assert res.ref == "repo@sha256:a"

    # ack ordering invariant: ZADD confirmed (durable) BEFORE XACK
    # After ack completes: confirmed-set has the digest; pending count is 0; stream is trimmed.
    adapter.ack(res, digest="sha256:a", attested_at="2024-01-01T00:00:00+00:00")

    score = redis_server.zscore("houba:scan:confirmed", "sha256:a")
    assert score is not None and score > 0.0  # RESP3: float epoch

    assert redis_server.xpending(WORK, GROUP)["pending"] == 0  # RESP3: int
    assert redis_server.xlen(WORK) == 0


def test_ack_score_is_epoch_from_iso_string(redis_server):
    """The confirmed-ZSET score must be a UNIX epoch derived from the ISO-8601 attested_at."""
    adapter = _make_adapter(redis_server)
    adapter.enqueue(["repo@sha256:c"])
    res = adapter.reserve(block_ms=100)
    assert res is not None

    # 2024-01-01T12:00:00+00:00 == 1704110400.0 UTC
    adapter.ack(res, digest="sha256:c", attested_at="2024-01-01T12:00:00+00:00")
    score = redis_server.zscore("houba:scan:confirmed", "sha256:c")
    assert score == pytest.approx(1704110400.0)


def test_reserve_returns_none_on_empty(redis_server):
    adapter = _make_adapter(redis_server)
    assert adapter.reserve(block_ms=50) is None


def test_reaper_reclaims_dropped_not_alive(redis_server):
    adapter = _make_adapter(redis_server, consumer="worker-dead")
    adapter.enqueue(["repo@sha256:a"])
    res = adapter.reserve(block_ms=100)
    assert res is not None

    reaper = _make_adapter(redis_server, consumer="reaper")
    claimed = reaper.reaper(min_idle_ms=MIN_IDLE_MS, max_deliveries=3)
    assert claimed == []

    time.sleep((MIN_IDLE_MS + 200) / 1000)
    claimed = reaper.reaper(min_idle_ms=MIN_IDLE_MS, max_deliveries=3)
    assert claimed == [res.token]

    rng = redis_server.xpending_range(WORK, GROUP, min=res.token, max=res.token, count=1)
    assert rng[0]["times_delivered"] == 2  # RESP3: int


def test_reaper_dead_letters_past_max(redis_server):
    adapter = _make_adapter(redis_server, consumer="w")
    adapter.enqueue(["repo@sha256:poison"])
    adapter.reserve(block_ms=100)

    reaper = _make_adapter(redis_server, consumer="reaper")
    for _ in range(4):
        time.sleep((MIN_IDLE_MS + 50) / 1000)
        reaper.reaper(min_idle_ms=MIN_IDLE_MS, max_deliveries=3)

    assert redis_server.xlen(DEAD) == 1  # RESP3: int
    assert redis_server.xpending(WORK, GROUP)["pending"] == 0


def test_trim_minid_keeps_unacked(redis_server):
    adapter = _make_adapter(redis_server, consumer="w")
    adapter.enqueue(["repo@sha256:a", "repo@sha256:b"])
    res_a = adapter.reserve(block_ms=100)
    res_b = adapter.reserve(block_ms=100)
    assert res_a is not None and res_b is not None

    adapter.ack(res_a, digest="sha256:a", attested_at="2024-01-01T00:00:00+00:00")
    survivors = [mid for mid, _ in redis_server.xrange(WORK)]
    assert res_a.token not in survivors
    assert res_b.token in survivors


def test_coverage_check_returns_gap(redis_server):
    redis_server.zadd("houba:scan:confirmed", {"sha256:b": 5000})
    adapter = _make_adapter(redis_server)
    gap = adapter.coverage_check(["sha256:a", "sha256:b"], max_age_s=10_000, now=10_000)
    assert gap == ["sha256:a"]


def test_trim_keeps_unread_same_ms_sibling(redis_server):
    redis_server.xadd(WORK, {"ref": "repo@sha256:a"}, id="100-0")
    redis_server.xadd(WORK, {"ref": "repo@sha256:b"}, id="100-1")  # un-read, SAME ms as acked

    adapter = _make_adapter(redis_server, consumer="w")
    res = adapter.reserve(block_ms=100)  # reads 100-0 only
    assert res is not None
    assert res.token == "100-0"

    adapter.ack(res, digest="sha256:a", attested_at="2024-01-01T00:00:00+00:00")
    survivors = [mid for mid, _ in redis_server.xrange(WORK)]
    assert "100-1" in survivors  # the un-read sibling must NOT be trimmed


def test_ensure_group_idempotent(redis_server):
    # First adapter calls ensure_group in __init__
    adapter = _make_adapter(redis_server)
    # Second construction with same group must not raise (BUSYGROUP swallowed)
    _make_adapter(redis_server, consumer="worker-2")
    adapter.enqueue(["repo@sha256:a"])
    assert redis_server.xlen(WORK) == 1


def test_dlq_replay_moves_back_to_work(redis_server):
    adapter = _make_adapter(redis_server)
    redis_server.xadd(DEAD, {"ref": "repo@sha256:x", "error": "503", "stage": "scan"})
    moved = adapter.dlq_replay("sha256:x")
    assert moved == 1
    assert redis_server.xlen(DEAD) == 0
    assert [m[1]["ref"] for m in redis_server.xrange(WORK)] == ["repo@sha256:x"]


def test_dlq_list_returns_entries_with_id(redis_server):
    adapter = _make_adapter(redis_server)
    redis_server.xadd(DEAD, {"ref": "repo@sha256:x", "error": "503"})
    redis_server.xadd(DEAD, {"ref": "repo@sha256:y", "error": "504"})
    entries = adapter.dlq_list()
    assert len(entries) == 2
    for entry in entries:
        assert "id" in entry  # RESP3 shape: id key injected by dlq_list
        assert "ref" in entry
        assert "error" in entry


def test_dlq_drop_removes_matching_entries(redis_server):
    adapter = _make_adapter(redis_server)
    redis_server.xadd(DEAD, {"ref": "repo@sha256:x", "error": "503"})
    redis_server.xadd(DEAD, {"ref": "repo@sha256:y", "error": "504"})
    dropped = adapter.dlq_drop("sha256:x")
    assert dropped == 1
    assert redis_server.xlen(DEAD) == 1
    remaining = [m[1]["ref"] for m in redis_server.xrange(DEAD)]
    assert remaining == ["repo@sha256:y"]


def test_dlq_drop_all_selector(redis_server):
    adapter = _make_adapter(redis_server)
    redis_server.xadd(DEAD, {"ref": "repo@sha256:x", "error": "503"})
    redis_server.xadd(DEAD, {"ref": "repo@sha256:y", "error": "504"})
    dropped = adapter.dlq_drop("--all")
    assert dropped == 2
    assert redis_server.xlen(DEAD) == 0


def test_dead_letter_writes_dead_before_xack(redis_server):
    """INVARIANT: XADD dead (durable) happens before XACK work.
    Outcome assertion: after dead_letter the entry is in dead AND no longer pending."""
    adapter = _make_adapter(redis_server)
    adapter.enqueue(["repo@sha256:fail"])
    res = adapter.reserve(block_ms=100)
    assert res is not None
    assert redis_server.xpending(WORK, GROUP)["pending"] == 1

    adapter.dead_letter(res, ref="repo@sha256:fail", reason={"error": "permanent", "stage": "scan"})

    dead_entries = redis_server.xrange(DEAD)
    assert len(dead_entries) == 1
    _, fields = dead_entries[0]
    assert fields["ref"] == "repo@sha256:fail"
    assert fields["error"] == "permanent"
    assert redis_server.xpending(WORK, GROUP)["pending"] == 0
