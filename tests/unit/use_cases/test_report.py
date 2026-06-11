from __future__ import annotations

import json

from houba.ports.reporter import Counts, ErrorInfo
from houba.use_cases.report import (
    Operation,
    PolicyReport,
    RunReport,
    TargetReport,
    VariantReport,
    report_exit_code,
    run_report_json_schema,
)


def _ok_policy() -> PolicyReport:
    op = Operation(
        kind="imported", out_tag="7.2.0", src_tag="7.2.0", digest="sha256:a", applied=True
    )
    variant = VariantReport(name="v7", suffix="", totals=Counts(imported=1), operations=[op])
    target = TargetReport(dest_repo="harbor.corp/lib/redis", variants=[variant], operations=[])
    return PolicyReport(
        name="redis",
        source="docker.io/library/redis",
        status="ok",
        error=None,
        totals=Counts(imported=1),
        targets=[target],
    )


def test_run_report_round_trips_to_json() -> None:
    report = RunReport(
        mode="apply", status="ok", totals=Counts(imported=1), policies=[_ok_policy()]
    )
    payload = json.loads(report.model_dump_json())
    assert payload["status"] == "ok"
    assert (
        payload["policies"][0]["targets"][0]["variants"][0]["operations"][0]["kind"] == "imported"
    )
    assert payload["totals"]["imported"] == 1


def test_report_exit_code_zero_when_all_ok() -> None:
    report = RunReport(mode="apply", status="ok", totals=Counts(), policies=[_ok_policy()])
    assert report_exit_code(report) == 0


def test_report_exit_code_is_max_of_failures() -> None:
    p_adapter = PolicyReport(
        name="a",
        source="s",
        status="failed",
        error=ErrorInfo(type="RegctlError", message="boom", exit_code=2),
        totals=Counts(),
        targets=[],
    )
    p_internal = PolicyReport(
        name="b",
        source="s",
        status="failed",
        error=ErrorInfo(type="RuntimeError", message="ugh", exit_code=4),
        totals=Counts(),
        targets=[],
    )
    report = RunReport(
        mode="apply", status="failed", totals=Counts(), policies=[p_adapter, p_internal]
    )
    assert report_exit_code(report) == 4


def test_json_schema_is_stable_and_serializable() -> None:
    json.dumps(run_report_json_schema())
    assert run_report_json_schema()["title"] == "RunReport"
