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
