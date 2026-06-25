import time

from scripts import scan_streams

WORK = "houba:scan:work"
DEAD = "houba:scan:dead"
GROUP = "scan"


def test_enqueue_xadds_each_ref(redis_server):
    r = redis_server
    scan_streams.ensure_group(r, WORK, GROUP)
    scan_streams.enqueue(r, WORK, ["repo@sha256:a", "repo@sha256:b"])
    assert r.xlen(WORK) == 2
    msgs = r.xrange(WORK)
    assert [m[1]["ref"] for m in msgs] == ["repo@sha256:a", "repo@sha256:b"]


def test_reserve_then_ack_confirms_and_trims(redis_server):
    r = redis_server
    scan_streams.ensure_group(r, WORK, GROUP)
    scan_streams.enqueue(r, WORK, ["repo@sha256:a"])
    resv = scan_streams.reserve(r, "worker-1")
    assert resv is not None
    msg_id, ref = resv
    assert ref == "repo@sha256:a"
    scan_streams.ack(r, msg_id, digest="sha256:a", attested_at=1000)
    assert r.zscore("houba:scan:confirmed", "sha256:a") == 1000
    assert r.xpending(WORK, GROUP)["pending"] == 0
    assert r.xlen(WORK) == 0


def test_reserve_returns_none_on_empty(redis_server):
    r = redis_server
    scan_streams.ensure_group(r, WORK, GROUP)
    assert scan_streams.reserve(r, "worker-1", block_ms=50) is None


MIN_IDLE_MS = 300


def test_reaper_reclaims_dropped_not_alive(redis_server):
    r = redis_server
    scan_streams.ensure_group(r, WORK, GROUP)
    scan_streams.enqueue(r, WORK, ["repo@sha256:a"])
    msg_id, _ = scan_streams.reserve(r, "worker-dead")
    claimed = scan_streams.reaper(r, "reaper", min_idle_ms=MIN_IDLE_MS, max_deliveries=3)
    assert claimed == []
    time.sleep((MIN_IDLE_MS + 200) / 1000)
    claimed = scan_streams.reaper(r, "reaper", min_idle_ms=MIN_IDLE_MS, max_deliveries=3)
    assert claimed == [msg_id]
    rng = r.xpending_range(WORK, GROUP, min=msg_id, max=msg_id, count=1)
    assert rng[0]["times_delivered"] == 2


def test_reaper_dead_letters_past_max(redis_server):
    r = redis_server
    scan_streams.ensure_group(r, WORK, GROUP)
    scan_streams.enqueue(r, WORK, ["repo@sha256:poison"])
    scan_streams.reserve(r, "w")
    for _ in range(4):
        time.sleep((MIN_IDLE_MS + 50) / 1000)
        scan_streams.reaper(
            r, "reaper", min_idle_ms=MIN_IDLE_MS, max_deliveries=3, reason={"error": "503"}
        )
    assert r.xlen(DEAD) == 1
    assert r.xpending(WORK, GROUP)["pending"] == 0


def test_trim_minid_keeps_unacked(redis_server):
    r = redis_server
    scan_streams.ensure_group(r, WORK, GROUP)
    scan_streams.enqueue(r, WORK, ["repo@sha256:a", "repo@sha256:b"])
    id_a, _ = scan_streams.reserve(r, "w")
    id_b, _ = scan_streams.reserve(r, "w")
    scan_streams.ack(r, id_a, digest="sha256:a", attested_at=1)
    survivors = [mid for mid, _ in r.xrange(WORK)]
    assert id_a not in survivors
    assert id_b in survivors


def test_coverage_check_returns_gap(redis_server):
    r = redis_server
    r.zadd("houba:scan:confirmed", {"sha256:b": 5000})
    placed = {"sha256:a", "sha256:b"}
    gap = scan_streams.coverage_check(r, placed, max_age_s=10_000, now=10_000)
    assert gap == ["sha256:a"]
