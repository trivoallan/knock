from __future__ import annotations

import io
import json

from houba.cli.render import render_report
from houba.ports.reporter import Counts, ErrorInfo
from houba.use_cases.report import (
    Operation,
    PolicyReport,
    RunReport,
    TargetReport,
    VariantReport,
)


def _report(status: str = "ok") -> RunReport:
    op = Operation(
        kind="imported", out_tag="7.2.0", src_tag="7.2.0", digest="sha256:a", applied=True
    )
    variant = VariantReport(name="v7", suffix="", totals=Counts(imported=1), operations=[op])
    target = TargetReport(
        dest_repo="harbor.corp/lib/redis",
        variants=[variant],
        operations=[],
        totals=Counts(imported=1),
    )
    policy = PolicyReport(
        name="redis",
        source="docker.io/library/redis",
        status="ok",
        error=None,
        totals=Counts(imported=1),
        targets=[target],
    )
    return RunReport(mode="apply", status=status, totals=Counts(imported=1), policies=[policy])  # type: ignore[arg-type]


def test_render_json_is_machine_readable() -> None:
    buf = io.StringIO()
    render_report(_report(), fmt="json", verbose=False, stream=buf)
    payload = json.loads(buf.getvalue())
    assert payload["status"] == "ok"
    assert payload["policies"][0]["name"] == "redis"


def test_render_text_summary_lists_policy_and_totals() -> None:
    buf = io.StringIO()
    render_report(_report(), fmt="text", verbose=False, stream=buf)
    out = buf.getvalue()
    assert "redis" in out
    assert "imported=1" in out
    assert "reconcile [apply]" in out
    assert "status=ok" in out
    assert "7.2.0" not in out  # operations are hidden without --verbose


def test_render_text_verbose_unfolds_operations() -> None:
    buf = io.StringIO()
    render_report(_report(), fmt="text", verbose=True, stream=buf)
    out = buf.getvalue()
    assert "harbor.corp/lib/redis" in out
    assert "imported" in out
    assert "7.2.0" in out


def test_render_text_marks_failed_policy() -> None:
    failed = PolicyReport(
        name="nginx",
        source="docker.io/library/nginx",
        status="failed",
        error=ErrorInfo("RegctlError", "boom", 2),
        totals=Counts(),
        targets=[],
    )
    report = RunReport(mode="apply", status="partial", totals=Counts(), policies=[failed])  # type: ignore[arg-type]
    buf = io.StringIO()
    render_report(report, fmt="text", verbose=False, stream=buf)
    out = buf.getvalue()
    assert "FAILED" in out
    assert "RegctlError" in out
    assert "boom" in out
