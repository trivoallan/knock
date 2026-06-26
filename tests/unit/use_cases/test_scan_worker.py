from datetime import UTC, datetime

from houba.use_cases.scan_worker import process_one
from tests.fakes.queue import FakeQueuePort


class _Outcome:
    def __init__(self, digest, ts):
        self.subject_digest = digest
        self.timestamp = ts


def test_success_acks_with_attest_timestamp():
    q = FakeQueuePort(work=["reg/app@sha256:abc"])
    signed = datetime(2026, 6, 26, tzinfo=UTC)
    handled = process_one(
        q, scan_and_attach=lambda ref: _Outcome("sha256:abc", signed), max_deliveries=3
    )
    assert handled is True
    assert q.acked == [("sha256:abc", signed.isoformat())]
    assert q.dead_lettered == []


def test_empty_queue_returns_false():
    q = FakeQueuePort(work=[])
    assert process_one(q, scan_and_attach=lambda ref: None, max_deliveries=3) is False


def test_permanent_failure_dead_letters():
    q = FakeQueuePort(work=["reg/app@sha256:def"])
    def boom(ref):
        raise RuntimeError("manifest unknown: 404")  # classify_exception -> permanent
    handled = process_one(q, scan_and_attach=boom, max_deliveries=3)
    assert handled is True
    assert q.acked == []
    assert len(q.dead_lettered) == 1
    ref, reason = q.dead_lettered[0]
    assert ref == "reg/app@sha256:def" and reason["kind"] == "permanent"


def test_transient_failure_leaves_pending():
    q = FakeQueuePort(work=["reg/app@sha256:eee"])
    def flaky(ref):
        raise RuntimeError("registry 503 service unavailable")  # transient
    handled = process_one(q, scan_and_attach=flaky, max_deliveries=3)
    assert handled is True
    assert q.acked == [] and q.dead_lettered == []  # left pending for the reaper


def test_missing_sbom_referrer_is_transient():
    q = FakeQueuePort(work=["reg/app@sha256:fff"])
    # scan_and_attach returns None to signal "no SBOM referrer yet"
    handled = process_one(q, scan_and_attach=lambda ref: None, max_deliveries=3)
    assert handled is True
    assert q.acked == [] and q.dead_lettered == []
