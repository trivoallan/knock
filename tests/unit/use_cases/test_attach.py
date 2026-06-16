from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from houba.config import RegistryConfig
from houba.domain.scan.summary import Severity
from houba.errors import ConfigError, CosignError, UnknownFormatError
from houba.ports.registry import ImageInfo
from houba.use_cases.attach import (
    SCAN_RESULT_ARTIFACT_TYPE,
    ScanOutcome,
    attach_exit_code,
    attach_scan,
)
from tests.fakes.attestor import FakeAttestor
from tests.fakes.clock import FakeClock
from tests.fakes.registry import FakeRegistryPort

TS = datetime(2026, 6, 12, 9, 0, tzinfo=UTC)
REF = "harbor.corp/lib/redis:7.2.0"
SARIF = json.dumps(
    {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "trivy",
                        "version": "0.50.1",
                        "rules": [{"id": "CVE-1", "properties": {"security-severity": "9.9"}}],
                    }
                },
                "results": [{"ruleId": "CVE-1"}],
            }
        ],
    }
).encode()


def _registry() -> FakeRegistryPort:
    return FakeRegistryPort(
        infos={REF: ImageInfo(digest="sha256:abc", created=None, annotations={})}
    )


def test_attach_stamps_referrer_on_digest() -> None:
    reg = _registry()
    outcome = attach_scan(REF, SARIF, registry=reg, clock=FakeClock(TS), label_prefix="io.houba")
    assert outcome.subject_digest == "sha256:abc"
    assert outcome.tool == "trivy"
    assert outcome.format == "sarif"
    assert outcome.facts["vuln.critical"] == "1"
    # one referrer attached to the digest-pinned subject
    (subject, atype, media, blob, annotations) = reg.artifact_referrers[0]
    assert subject == "harbor.corp/lib/redis@sha256:abc"
    assert atype == SCAN_RESULT_ARTIFACT_TYPE
    assert media == "application/sarif+json"
    assert blob == SARIF
    assert annotations["io.houba.scan.vuln.critical"] == "1"
    assert annotations["io.houba.scan.subject"] == "sha256:abc"
    assert outcome.referrer_digest.startswith("sha256:")


def test_attach_unknown_format_raises() -> None:
    reg = _registry()
    with pytest.raises(UnknownFormatError):
        attach_scan(REF, b"not json", registry=reg, clock=FakeClock(TS), label_prefix="io.houba")


def test_attach_signs_when_attestor_present() -> None:
    reg = _registry()
    att = FakeAttestor()
    outcome = attach_scan(
        REF,
        SARIF,
        registry=reg,
        clock=FakeClock(TS),
        label_prefix="io.houba",
        attestor=att,
        builder_id="houba://ci",
    )
    assert outcome.attestation is not None
    assert outcome.attestation.predicate_type == "https://houba.dev/predicate/scan/v1"
    assert len(att.attested) == 1
    subject, statement = att.attested[0]
    assert subject == "harbor.corp/lib/redis@sha256:abc"
    assert statement["predicateType"] == "https://houba.dev/predicate/scan/v1"
    assert statement["predicate"]["report_digest"] == outcome.referrer_digest
    assert statement["predicate"]["scanner"]["name"] == "trivy"


def test_attach_no_attestor_no_attestation() -> None:
    reg = _registry()
    outcome = attach_scan(REF, SARIF, registry=reg, clock=FakeClock(TS), label_prefix="io.houba")
    assert outcome.attestation is None
    assert reg.artifact_referrers  # the raw referrer is still attached


def test_attach_signing_failure_propagates_after_referrer_attached() -> None:
    reg = _registry()
    att = FakeAttestor(fail=True)
    with pytest.raises(CosignError):
        attach_scan(
            REF,
            SARIF,
            registry=reg,
            clock=FakeClock(TS),
            label_prefix="io.houba",
            attestor=att,
        )
    assert reg.artifact_referrers  # raw referrer attached before the signing attempt


def _outcome(**counts: int) -> ScanOutcome:
    facts = {f"vuln.{s.value}": "0" for s in Severity}
    facts.update({f"vuln.{k}": str(v) for k, v in counts.items()})
    return ScanOutcome(
        subject_digest="sha256:s",
        referrer_digest="sha256:r",
        tool="trivy",
        tool_version="1",
        format="sarif",
        facts=facts,
        timestamp=datetime(2026, 6, 15, tzinfo=UTC),
    )


def test_attach_exit_code_gates_on_breach() -> None:
    assert attach_exit_code(_outcome(critical=1), fail_on=Severity.high) == 1
    assert attach_exit_code(_outcome(medium=1), fail_on=Severity.high) == 0


def test_attach_exit_code_none_never_gates() -> None:
    assert attach_exit_code(_outcome(critical=99), fail_on=None) == 0


def _roster_for_attach() -> dict[str, RegistryConfig]:
    return {"prod": RegistryConfig(host="harbor.corp", username="u", password="p")}


def test_attach_runs_session_on_host_match() -> None:
    reg = _registry()
    attach_scan(
        REF,
        SARIF,
        registry=reg,
        clock=FakeClock(TS),
        label_prefix="io.houba",
        roster=_roster_for_attach(),
    )
    assert reg.configured == [("harbor.corp", True, None)]
    assert reg.logins == [("harbor.corp", "u", True)]


def test_attach_no_session_when_host_not_in_roster() -> None:
    reg = _registry()
    attach_scan(
        REF,
        SARIF,
        registry=reg,
        clock=FakeClock(TS),
        label_prefix="io.houba",
        roster={},
    )
    assert reg.configured == []
    assert reg.logins == []


def test_attach_registry_override_selects_entry() -> None:
    reg = _registry()
    roster = {"other": RegistryConfig(host="harbor.corp", username="u", password="p")}
    attach_scan(
        REF,
        SARIF,
        registry=reg,
        clock=FakeClock(TS),
        label_prefix="io.houba",
        roster=roster,
        registry_override="other",
    )
    assert reg.logins == [("harbor.corp", "u", True)]


def test_attach_unknown_registry_override_raises() -> None:
    reg = _registry()
    with pytest.raises(ConfigError):
        attach_scan(
            REF,
            SARIF,
            registry=reg,
            clock=FakeClock(TS),
            label_prefix="io.houba",
            roster=_roster_for_attach(),
            registry_override="nope",
        )
