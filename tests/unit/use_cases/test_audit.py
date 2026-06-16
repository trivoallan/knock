from __future__ import annotations

import json

import pytest

from houba.config import RegistryConfig
from houba.domain.attestation import COSIGN_ATTESTATION_ARTIFACT_TYPE
from houba.errors import ConfigError
from houba.ports.registry import Referrer
from houba.use_cases.audit import (
    audit_coverage,
    audit_exit_code,
    coverage_report_json_schema,
)
from tests.fakes.registry import FakeRegistryPort

_ROSTER = {"harbor": RegistryConfig(host="harbor.example")}
_HOST = "harbor.example"
_REPO = f"{_HOST}/lib/redis"


def _cosign_ref(subject: str) -> Referrer:
    return Referrer(
        digest="sha256:sig",
        artifact_type=COSIGN_ATTESTATION_ARTIFACT_TYPE,
        annotations={},
        subject_tag=subject,
    )


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


def test_check_signed_off_leaves_signed_none() -> None:
    report = audit_coverage(
        registry=_reg(), roster=_ROSTER, only_registry=None, label_prefix="io.houba"
    )
    assert all(o.signed is None for o in report.outcomes)
    assert report.counts.signed == 0
    assert report.counts.unsigned == 0


def test_check_signed_probes_only_covered_images() -> None:
    reg = _reg(referrers={f"{_REPO}:7.1": [_cosign_ref(f"{_REPO}:7.1")]})
    report = audit_coverage(
        registry=reg,
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        check_signed=True,
    )
    by = {o.image_ref: o for o in report.outcomes}
    assert by[f"{_REPO}:7.1"].signed is True  # covered + has cosign referrer
    assert by[f"{_REPO}:7.2"].signed is None  # uncovered -> not probed
    assert report.counts.signed == 1
    assert report.counts.unsigned == 0


def test_check_signed_covered_without_referrer_is_unsigned() -> None:
    report = audit_coverage(
        registry=_reg(),  # no referrers seeded
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        check_signed=True,
    )
    by = {o.image_ref: o for o in report.outcomes}
    assert by[f"{_REPO}:7.1"].signed is False
    assert report.counts.signed == 0
    assert report.counts.unsigned == 1


def test_fail_on_unsigned_gate() -> None:
    report = audit_coverage(
        registry=_reg(),  # 7.1 covered-but-unsigned, 7.2 uncovered
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        check_signed=True,
    )
    assert report.counts.unsigned == 1
    assert audit_exit_code(report, fail_on_uncovered=False, fail_on_unsigned=False) == 0
    assert audit_exit_code(report, fail_on_uncovered=False, fail_on_unsigned=True) == 1


def test_read_error_dominates_unsigned_gate() -> None:
    reg = _reg(fail_get={f"{_REPO}:7.1"})
    report = audit_coverage(
        registry=reg,
        roster=_ROSTER,
        only_registry=None,
        label_prefix="io.houba",
        check_signed=True,
    )
    # AdapterError -> 2 wins over the unsigned gate's 1
    assert audit_exit_code(report, fail_on_uncovered=False, fail_on_unsigned=True) == 2
