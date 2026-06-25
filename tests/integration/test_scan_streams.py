from scripts import scan_streams

WORK = "houba:scan:work"
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
