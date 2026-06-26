from tests.fakes.queue import FakeQueuePort


def test_reserve_then_ack_journals():
    q = FakeQueuePort(work=["reg/app@sha256:abc"])
    res = q.reserve()
    assert res is not None and res.ref == "reg/app@sha256:abc"
    q.ack(res, digest="sha256:abc", attested_at="2026-06-26T00:00:00+00:00")
    assert q.acked == [("sha256:abc", "2026-06-26T00:00:00+00:00")]
    assert q.reserve() is None  # work drained


def test_dead_letter_journals():
    q = FakeQueuePort(work=["reg/app@sha256:def"])
    res = q.reserve()
    assert res is not None
    q.dead_letter(res, ref=res.ref, reason={"error": "manifest unknown"})
    assert q.dead_lettered == [("reg/app@sha256:def", {"error": "manifest unknown"})]
