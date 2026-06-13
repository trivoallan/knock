from __future__ import annotations

import json

import pytest

from houba.config import RegistryConfig
from houba.errors import ConfigError
from houba.use_cases.audit import (
    audit_coverage,
    audit_exit_code,
    coverage_report_json_schema,
)
from tests.fakes.registry import FakeRegistryPort

_ROSTER = {"harbor": RegistryConfig(host="harbor.example")}
_HOST = "harbor.example"
_REPO = f"{_HOST}/lib/redis"


def _reg(**kw: object) -> FakeRegistryPort:
    return FakeRegistryPort(
        repositories={_HOST: ["lib/redis"]},
        tags={_REPO: ["7.1", "7.2"]},
        annotations={
            f"{_REPO}:7.1": {"io.houba.policy": "redis"},  # covered
            f"{_REPO}:7.2": {},  # uncovered
        },
        **kw,
    )


def test_reports_covered_and_uncovered() -> None:
    report = audit_coverage(
        registry=_reg(), roster=_ROSTER, only_registry=None, label_prefix="io.houba"
    )
    by = {o.image_ref: o for o in report.outcomes}
    assert by[f"{_REPO}:7.1"].covered is True
    assert by[f"{_REPO}:7.1"].policy == "redis"
    assert by[f"{_REPO}:7.2"].covered is False
    assert by[f"{_REPO}:7.2"].policy is None
    assert report.counts.scanned == 2
    assert report.counts.covered == 1
    assert report.counts.uncovered == 1
    assert report.counts.errored == 0
    assert audit_exit_code(report, fail_on_uncovered=False) == 0
    assert audit_exit_code(report, fail_on_uncovered=True) == 1


def test_all_covered_passes_the_gate() -> None:
    reg = FakeRegistryPort(
        repositories={_HOST: ["lib/redis"]},
        tags={_REPO: ["7.1"]},
        annotations={f"{_REPO}:7.1": {"io.houba.policy": "redis"}},
    )
    report = audit_coverage(
        registry=reg, roster=_ROSTER, only_registry=None, label_prefix="io.houba"
    )
    assert report.counts.uncovered == 0
    assert audit_exit_code(report, fail_on_uncovered=True) == 0


def test_read_error_recorded_and_reddens_exit_without_blocking_siblings() -> None:
    reg = _reg(fail_get={f"{_REPO}:7.1"})
    report = audit_coverage(
        registry=reg, roster=_ROSTER, only_registry=None, label_prefix="io.houba"
    )
    errs = [o for o in report.outcomes if o.error is not None]
    assert [o.image_ref for o in errs] == [f"{_REPO}:7.1"]
    assert errs[0].error is not None and errs[0].error.type == "RegctlError"
    assert report.counts.errored == 1
    assert any(o.image_ref == f"{_REPO}:7.2" and not o.covered for o in report.outcomes)
    assert audit_exit_code(report, fail_on_uncovered=False) == 2  # AdapterError -> 2


def test_only_registry_restricts_to_one_host() -> None:
    report = audit_coverage(
        registry=_reg(), roster=_ROSTER, only_registry="harbor", label_prefix="io.houba"
    )
    assert report.registries == ["harbor.example"]


def test_unknown_only_registry_raises_config_error() -> None:
    with pytest.raises(ConfigError):
        audit_coverage(
            registry=_reg(), roster=_ROSTER, only_registry="nope", label_prefix="io.houba"
        )


def test_configure_and_login_once_per_host() -> None:
    reg = _reg()
    roster = {"harbor": RegistryConfig(host=_HOST, username="robot", password="s3cret")}
    audit_coverage(registry=reg, roster=roster, only_registry=None, label_prefix="io.houba")
    assert reg.configured == [(_HOST, True, None)]
    assert reg.logins == [(_HOST, "robot", True)]


def test_json_schema_is_stable_and_serializable() -> None:
    json.dumps(coverage_report_json_schema())
