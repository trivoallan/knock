from __future__ import annotations

import io
import json

from knock.adapters.structlog_reporter import StructlogReporter
from knock.logging import configure
from knock.ports.reporter import Counts, ErrorInfo, OperationEvent
from knock.use_cases.report import RunReport


def test_structlog_reporter_emits_json_events() -> None:
    buf = io.StringIO()
    configure(format_="json", level="INFO", stream=buf)
    r = StructlogReporter()
    r.run_started(1, mode="apply")
    r.operation_applied(
        OperationEvent(
            "redis", "harbor/lib/redis", "v7", "imported", "7.2.0", "7.2.0", "sha256:a", True
        )
    )
    r.policy_failed("nginx", ErrorInfo("RegctlError", "boom", 2))

    lines = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    events = {line["event"] for line in lines}
    assert "run.started" in events
    op = next(line for line in lines if line["event"] == "operation")
    assert op["kind"] == "imported"
    assert op["out_tag"] == "7.2.0"
    assert op["applied"] is True
    fail = next(line for line in lines if line["event"] == "policy.failed")
    assert fail["error_type"] == "RegctlError"
    assert fail["exit_code"] == 2


def test_structlog_reporter_renders_operation_failed() -> None:
    buf = io.StringIO()
    configure(format_="json", level="INFO", stream=buf)
    r = StructlogReporter()
    r.operation_failed(
        OperationEvent(
            "redis", "harbor/lib/redis", "v7", "imported", "7.3.0", "7.3.0", "sha256:b", False
        ),
        ErrorInfo("RegctlError", "boom", 2),
    )
    lines = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    rec = next(line for line in lines if line["event"] == "operation.failed")
    assert rec["out_tag"] == "7.3.0"
    assert rec["error_type"] == "RegctlError"
    assert rec["exit_code"] == 2


def test_structlog_reporter_surfaces_transform_steps_and_out_digest() -> None:
    buf = io.StringIO()
    configure(format_="json", level="INFO", stream=buf)
    r = StructlogReporter()
    # rebuild op: carries the applied steps + the produced (post-annotate) digest
    r.operation_applied(
        OperationEvent(
            "debian-tz",
            "reg/demo/debian",
            "eu",
            "imported",
            "bookworm-slim-eu",
            "bookworm-slim",
            "sha256:src",
            True,
            transform_steps=("setTimezone",),
            out_digest="sha256:out",
        )
    )
    # copy/skip op: no transform, nothing produced → keys are omitted entirely
    r.operation_applied(
        OperationEvent(
            "busybox",
            "reg/demo/busybox",
            "default",
            "skipped",
            "1.37",
            "1.37",
            "sha256:b",
            False,
        )
    )

    ops = [
        json.loads(line)
        for line in buf.getvalue().splitlines()
        if line.strip() and json.loads(line)["event"] == "operation"
    ]
    rebuilt, copied = ops[0], ops[1]
    assert rebuilt["transform_steps"] == ["setTimezone"]
    assert rebuilt["out_digest"] == "sha256:out"
    assert "transform_steps" not in copied
    assert "out_digest" not in copied


def test_structlog_reporter_completed_events_carry_all_counts() -> None:
    # The journal summary must not drop any Counts field — marked/attested/sbom were
    # missing, so operators tailing stderr couldn't see mark/attest/SBOM-backfill activity.
    buf = io.StringIO()
    configure(format_="json", level="INFO", stream=buf)
    totals = Counts(
        imported=1,
        updated=2,
        deleted=3,
        aliased=4,
        skipped=5,
        marked=6,
        attested=7,
        sbom=8,
        failed=9,
    )
    r = StructlogReporter()
    r.policy_completed("redis", totals)
    r.run_completed(RunReport(mode="apply", status="ok", totals=totals, policies=[]))

    lines = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    expected = {
        "imported": 1,
        "updated": 2,
        "deleted": 3,
        "aliased": 4,
        "skipped": 5,
        "marked": 6,
        "attested": 7,
        "sbom": 8,
        "failed": 9,
    }
    for event_name in ("policy.completed", "run.completed"):
        rec = next(line for line in lines if line["event"] == event_name)
        assert {k: rec[k] for k in expected} == expected, event_name


def test_structlog_reporter_text_mode_is_human_readable() -> None:
    buf = io.StringIO()
    configure(format_="text", level="INFO", stream=buf)
    StructlogReporter().policy_started("redis", "docker.io/library/redis")
    out = buf.getvalue()
    assert "policy.started" in out
    assert "redis" in out
