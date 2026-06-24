from datetime import UTC, datetime, timedelta

import pytest

from houba.domain.scan.summary import Severity
from houba.domain.verify import Requirement
from houba.errors import ConfigError
from houba.ports.attestor import VerifiedPredicate
from houba.ports.registry import Referrer
from tests.fakes.attestor import FakeAttestor
from tests.fakes.clock import FakeClock
from tests.fakes.registry import FakeRegistryPort

REF = "reg.example/app@sha256:" + "a" * 64
NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)


def _registry(*, annotations=None, referrers=None):
    return FakeRegistryPort(
        annotations={REF: annotations or {}},
        digests={REF: "sha256:" + "a" * 64},
        referrers={REF: referrers or []},
    )


def test_verify_scan_pass_green():
    from houba.use_cases.verify import verify_exit_code, verify_image

    attestor = FakeAttestor(
        predicates=[
            VerifiedPredicate(summary={"vuln.high": "0"}, attested_at="2026-06-24T11:00:00+00:00")
        ]
    )
    report = verify_image(
        REF,
        requirements={Requirement.scan_pass},
        registry=_registry(),
        attestor=attestor,
        clock=FakeClock(NOW),
        label_prefix="io.houba",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )
    assert report.passed is True
    assert verify_exit_code(report) == 1 - int(report.passed)  # 0 when passed
    assert attestor.verified == [(REF, "https://houba.dev/predicate/scan/v1")]


def test_verify_is_read_only():
    from houba.use_cases.verify import verify_image

    reg = _registry()
    verify_image(
        REF,
        requirements={Requirement.scan_pass},
        registry=reg,
        attestor=FakeAttestor(predicates=[]),
        clock=FakeClock(NOW),
        label_prefix="io.houba",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )
    assert reg.copied == [] and reg.annotated == [] and reg.deleted == []
    assert reg.marked == [] and reg.artifact_referrers == [] and reg.unmarked == []


def test_verify_stamp_and_sbom_presence():
    from houba.use_cases.verify import verify_image

    reg = _registry(
        annotations={"io.houba.artifact.type": "rebuild"},
        referrers=[
            Referrer(
                digest="sha256:b",
                artifact_type="application/spdx+json",
                annotations={},
                subject_tag="t",
            )
        ],
    )
    report = verify_image(
        REF,
        requirements={Requirement.stamp, Requirement.sbom},
        registry=reg,
        attestor=None,
        clock=FakeClock(NOW),
        label_prefix="io.houba",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )
    assert report.passed is True


def test_verify_scan_pass_without_attestor_is_config_error():
    from houba.use_cases.verify import verify_image

    with pytest.raises(ConfigError):
        verify_image(
            REF,
            requirements={Requirement.scan_pass},
            registry=_registry(),
            attestor=None,
            clock=FakeClock(NOW),
            label_prefix="io.houba",
            max_severity=Severity.high,
            max_age=timedelta(days=7),
        )


def test_verify_governed_without_attestor_is_config_error():
    from houba.use_cases.verify import verify_image

    with pytest.raises(ConfigError):
        verify_image(
            REF,
            requirements={Requirement.governed},
            registry=_registry(),
            attestor=None,
            clock=FakeClock(NOW),
            label_prefix="io.houba",
            max_severity=Severity.high,
            max_age=timedelta(days=7),
        )
