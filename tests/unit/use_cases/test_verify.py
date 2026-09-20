from datetime import UTC, datetime, timedelta

import pytest

from knock.domain.scan.summary import Severity
from knock.domain.verify import Requirement
from knock.errors import ConfigError
from knock.ports.attestor import VerifiedPredicate
from knock.ports.registry import Referrer
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
    from knock.use_cases.verify import verify_exit_code, verify_image

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
        label_prefix="io.knock",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )
    assert report.passed is True
    assert verify_exit_code(report) == 1 - int(report.passed)  # 0 when passed
    assert attestor.verified == [(REF, "https://knock.dev/predicate/scan/v1")]


def test_verify_is_read_only():
    from knock.use_cases.verify import verify_image

    reg = _registry()
    verify_image(
        REF,
        requirements={Requirement.scan_pass},
        registry=reg,
        attestor=FakeAttestor(predicates=[]),
        clock=FakeClock(NOW),
        label_prefix="io.knock",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )
    assert reg.copied == [] and reg.annotated == [] and reg.deleted == []
    assert reg.marked == [] and reg.artifact_referrers == [] and reg.unmarked == []


def test_verify_stamp_and_sbom_presence():
    from knock.use_cases.verify import verify_image

    reg = _registry(
        annotations={"io.knock.artifact.type": "rebuild"},
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
        label_prefix="io.knock",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )
    assert report.passed is True


def test_verify_scan_pass_without_attestor_is_config_error():
    from knock.use_cases.verify import verify_image

    with pytest.raises(ConfigError):
        verify_image(
            REF,
            requirements={Requirement.scan_pass},
            registry=_registry(),
            attestor=None,
            clock=FakeClock(NOW),
            label_prefix="io.knock",
            max_severity=Severity.high,
            max_age=timedelta(days=7),
        )


def _verify_signature(attestor):
    from knock.use_cases.verify import verify_image

    return verify_image(
        REF,
        requirements={Requirement.image_signature},
        registry=_registry(),
        attestor=attestor,
        clock=FakeClock(NOW),
        label_prefix="io.knock",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )


def test_verify_image_signature_reads_the_pinned_digest():
    attestor = FakeAttestor(image_signed=True)
    assert _verify_signature(attestor).passed is True
    assert attestor.signature_verified == [REF]


def test_verify_image_signature_fails_closed_when_unsigned():
    # e.g. an image carrying knock's attestations but never admitted
    assert _verify_signature(FakeAttestor(image_signed=False)).passed is False


def test_verify_image_signature_without_attestor_is_config_error():
    with pytest.raises(ConfigError, match="image-signature"):
        _verify_signature(None)


# A skill placed from git: an OCI artifact, not an image, addressed by its ref name.
SKILL_REF = "reg.example/skills/example-skill:v1.2.0"
SKILL_DIGEST = "sha256:" + "c" * 64


def _verify_skill_signature(attestor):
    from knock.use_cases.verify import verify_image

    return verify_image(
        SKILL_REF,
        requirements={Requirement.image_signature},
        registry=FakeRegistryPort(
            annotations={SKILL_REF: {"io.knock.artifact.type": "skill"}},
            digests={SKILL_REF: SKILL_DIGEST},
        ),
        attestor=attestor,
        clock=FakeClock(NOW),
        label_prefix="io.knock",
        max_severity=Severity.high,
        max_age=timedelta(days=7),
    )


def test_a_signed_skill_passes_the_signature_gate():
    # The gate takes no image-specific input: it pins the ref to its digest and asks
    # cosign. A skill placed by an `admit: true` policy is therefore promotable through
    # the same gate an image is.
    attestor = FakeAttestor(image_signed=True)
    report = _verify_skill_signature(attestor)
    assert report.passed is True
    # Pinned to the digest, so the verdict does not depend on where the alias points next.
    assert attestor.signature_verified == [f"reg.example/skills/example-skill@{SKILL_DIGEST}"]


def test_an_unsigned_skill_fails_the_signature_gate():
    from knock.use_cases.verify import verify_exit_code

    report = _verify_skill_signature(FakeAttestor(image_signed=False))
    assert report.passed is False
    assert verify_exit_code(report) == 1
