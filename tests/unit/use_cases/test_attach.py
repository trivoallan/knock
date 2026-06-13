from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from houba.errors import UnknownFormatError
from houba.ports.registry import ImageInfo
from houba.use_cases.attach import SCAN_RESULT_ARTIFACT_TYPE, attach_scan
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
    (subject, atype, media, blob, annotations) = reg.referrers[0]
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
