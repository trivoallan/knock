from __future__ import annotations

import io
import json

from houba.adapters.structlog_reporter import StructlogReporter
from houba.logging import configure
from houba.ports.reporter import Counts, ErrorInfo, OperationEvent


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


def test_structlog_reporter_text_mode_is_human_readable() -> None:
    buf = io.StringIO()
    configure(format_="text", level="INFO", stream=buf)
    StructlogReporter().policy_started("redis", "docker.io/library/redis")
    out = buf.getvalue()
    assert "policy.started" in out
    assert "redis" in out
