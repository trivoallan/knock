from __future__ import annotations

from knock.ports.reporter import Counts, ErrorInfo, OperationEvent
from knock.use_cases.report import RunReport
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


def test_fake_reporter_journals_run_completed() -> None:
    r = FakeReporter()
    report = RunReport(mode="apply", status="ok", totals=Counts(), policies=[])
    r.run_completed(report)
    assert r.runs_completed == [report]


def test_fake_reporter_journals_operation_failed() -> None:
    from knock.ports.reporter import OperationEvent

    r = FakeReporter()
    ev = OperationEvent(
        policy="redis",
        dest_repo="harbor.corp/lib/redis",
        variant="v7",
        kind="imported",
        out_tag="7.3.0",
        src_tag="7.3.0",
        digest="sha256:b",
        applied=False,
    )
    err = ErrorInfo("RegctlError", "boom", 2)
    r.operation_failed(ev, err)
    assert r.operation_failures == [(ev, err)]
