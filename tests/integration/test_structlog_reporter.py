from __future__ import annotations

import io
import json

from houba.adapters.structlog_reporter import StructlogReporter
from houba.logging import configure
from houba.ports.reporter import ErrorInfo, OperationEvent


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


def test_structlog_reporter_text_mode_is_human_readable() -> None:
    buf = io.StringIO()
    configure(format_="text", level="INFO", stream=buf)
    StructlogReporter().policy_started("redis", "docker.io/library/redis")
    out = buf.getvalue()
    assert "policy.started" in out
    assert "redis" in out
