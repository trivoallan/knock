from __future__ import annotations

from houba.ports.reporter import Counts, ErrorInfo, OperationEvent
from tests.fakes.reporter import FakeReporter


def test_fake_reporter_journals_calls() -> None:
    r = FakeReporter()
    r.run_started(2, mode="apply")
    r.policy_started("redis", "docker.io/library/redis")
    ev = OperationEvent(
        "redis", "harbor/lib/redis", "v7", "imported", "7.2.0", "7.2.0", "sha256:a", True
    )
    r.operation_applied(ev)
    r.policy_failed("nginx", ErrorInfo("RegctlError", "boom", 2))
    r.policy_completed("redis", Counts(imported=1))

    assert r.runs_started == [(2, "apply")]
    assert r.policies_started == [("redis", "docker.io/library/redis")]
    assert r.operations == [ev]
    assert r.failures == [("nginx", ErrorInfo("RegctlError", "boom", 2))]
    assert r.policies_completed == [("redis", Counts(imported=1))]
