"""Stage -> scan -> promote: per-destination vuln gate in the reconcile use case.

When a destination declares enforceFrom/auditFrom, reconcile builds/copies to a
staging tag, generates the SBOM, evaluates it, and only promotes the staging tag
to the public out_tag when the gate is not breached at enforce level. The staging
tag never outlives the operation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from houba.config import CACertSource, PackageMirror, RegistryConfig
from houba.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from houba.domain.scan.constants import SCAN_RESULT_ARTIFACT_TYPE
from houba.errors import ConfigError
from houba.ports.registry import ImageInfo
from houba.use_cases.reconcile import reconcile_policies
from houba.use_cases.report import RunReport
from tests.fakes.attestor import FakeAttestor
from tests.fakes.image_builder import FakeImageBuilder
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter
from tests.fakes.sbom_generator import FakeSbomGenerator
from tests.fakes.vuln import FakeVulnEvaluatorPort

NOW = datetime(2026, 6, 18, tzinfo=UTC)

SPDX = "application/spdx+json"
SARIF_MEDIA = "application/sarif+json"

SRC = "docker.io/library/busybox"
DEST = "reg.local/demo/busybox"
OUT_TAG = "1.36.0"
STAGING = f"{OUT_TAG}.houba-staging"

# SARIF fixtures, classified by SarifMapper into vuln.* buckets.
SARIF_CRITICAL = (
    b'{"runs":[{"tool":{"driver":{"name":"grype","version":"0.74.0"}},'
    b'"results":[{"ruleId":"CVE-1","level":"error",'
    b'"properties":{"security-severity":"9.8"}}]}]}'
)
SARIF_HIGH = (
    b'{"runs":[{"tool":{"driver":{"name":"grype","version":"0.74.0"}},'
    b'"results":[{"ruleId":"CVE-2","level":"error",'
    b'"properties":{"security-severity":"7.5"}}]}]}'
)
SARIF_CLEAN = b'{"runs":[{"tool":{"driver":{"name":"grype","version":"0.74.0"}},"results":[]}]}'


def _policy(*, enforce: str | None = None, audit: str | None = None) -> MirrorPolicy:
    dest = "{ project: demo, repository: busybox"
    if enforce is not None:
        dest += f", enforceFrom: {enforce}"
    if audit is not None:
        dest += f", auditFrom: {audit}"
    dest += " }"
    return parse_mirror_policy(
        f"""
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata: {{ name: busybox-copy }}
spec:
  artifactType: image
  source: {{ registry: docker.io, repository: library/busybox }}
  imports:
    - name: stable
      tags: {{ includeRegex: "^1\\\\.36\\\\.0$" }}
      destinations: [{dest}]
"""
    )


def _registry() -> FakeRegistryPort:
    return FakeRegistryPort(
        tags={SRC: [OUT_TAG], DEST: []},
        infos={f"{SRC}:{OUT_TAG}": ImageInfo(digest="sha256:bbsrc", created=NOW, annotations={})},
    )


def _run(policy: MirrorPolicy, registry: FakeRegistryPort, **over: object) -> RunReport:
    kwargs: dict[str, object] = dict(
        registry=registry,
        builder=FakeImageBuilder(),
        roster={"local": RegistryConfig(host="reg.local")},
        ca_certs={"corp": CACertSource(pem="PEMDATA")},
        package_mirrors={"corp": PackageMirror(apt="https://mirror.corp")},
        build_platform="linux/amd64",
        now=NOW,
        label_prefix="io.houba",
        dry_run_tags=False,
        dry_run_deletions=False,
        reporter=FakeReporter(),
        sbom_generator=FakeSbomGenerator(),
        sbom_formats=["spdx-json"],
    )
    kwargs.update(over)
    return reconcile_policies([policy], **kwargs)  # type: ignore[arg-type]


def _staged_digest(registry: FakeRegistryPort) -> str:
    """The deterministic fake digest produced by annotating the staging ref."""
    return registry.annotate(f"{DEST}:{STAGING}", {})


def _scan_referrers(registry: FakeRegistryPort, subject: str) -> list[tuple[str, str]]:
    # artifact_referrers entries: (image_ref, artifact_type, media_type, blob, annotations)
    return [
        (r[1], r[2])
        for r in registry.artifact_referrers
        if r[0] == subject and r[1] == SCAN_RESULT_ARTIFACT_TYPE
    ]


def test_enforce_breached_does_not_promote() -> None:
    registry = _registry()
    reporter = FakeReporter()
    report = _run(
        _policy(enforce="high"),
        registry,
        reporter=reporter,
        vuln_evaluator=FakeVulnEvaluatorPort(sarif=SARIF_CRITICAL),
    )

    # Staging copy happened, but the public out_tag was never promoted.
    assert (f"{SRC}:{OUT_TAG}", f"{DEST}:{STAGING}") in registry.copied
    assert (f"{DEST}:{STAGING}", f"{DEST}:{OUT_TAG}") not in registry.copied
    # Staging tag was cleaned up exactly once (no double-delete on the block path).
    assert registry.deleted.count(f"{DEST}:{STAGING}") == 1
    # No SBOM/SARIF referrer ever published for a blocked image.
    assert registry.artifact_referrers == []
    # The op was recorded as failed (gate blocked) with the precise ErrorInfo contract.
    assert report.totals.imported == 0
    assert report.totals.failed == 1
    assert report.status != "ok"
    (_ev, err) = reporter.operation_failures[0]
    assert err.type == "ScanGateBlocked"
    assert err.exit_code == 1
    assert err.message == "blocked: scan breached enforceFrom=high"


def test_audit_breached_promotes_with_breach_surfaced(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = _registry()
    reporter = FakeReporter()
    with caplog.at_level("WARNING"):
        report = _run(
            _policy(audit="high"),
            registry,
            reporter=reporter,
            vuln_evaluator=FakeVulnEvaluatorPort(sarif=SARIF_HIGH),
        )

    # Promoted: staging copied to the public out_tag.
    assert (f"{DEST}:{STAGING}", f"{DEST}:{OUT_TAG}") in registry.copied
    assert report.totals.imported == 1
    # SARIF referrer attached on the staged digest.
    subject = f"{DEST}@{_staged_digest(registry)}"
    assert (SCAN_RESULT_ARTIFACT_TYPE, SARIF_MEDIA) in _scan_referrers(registry, subject)
    # Staging tag cleaned up after promotion.
    assert f"{DEST}:{STAGING}" in registry.deleted
    # Breach surfaced as a warning (human-facing log stays).
    assert any("audit" in r.message.lower() for r in caplog.records)
    # Breach is also visible in the structured OperationEvent (queryable run report).
    assert len(reporter.operations) == 1
    assert reporter.operations[0].audit_breached is True


def test_clean_promotes_and_signs_scan_predicate() -> None:
    registry = _registry()
    attestor = FakeAttestor()
    reporter = FakeReporter()
    report = _run(
        _policy(enforce="critical"),
        registry,
        reporter=reporter,
        attestor=attestor,
        attest_builder_id="houba://test",
        vuln_evaluator=FakeVulnEvaluatorPort(sarif=SARIF_CLEAN),
    )

    assert (f"{DEST}:{STAGING}", f"{DEST}:{OUT_TAG}") in registry.copied
    assert report.totals.imported == 1
    subject = f"{DEST}@{_staged_digest(registry)}"
    assert (SCAN_RESULT_ARTIFACT_TYPE, SARIF_MEDIA) in _scan_referrers(registry, subject)
    # The scan predicate was signed (in-toto statement with the scan predicateType).
    scan_preds = [
        st for _ref, st in attestor.attested if "scan" in str(st.get("predicateType", "")).lower()
    ]
    assert len(scan_preds) == 1
    assert scan_preds[0]["subject"][0]["name"] == f"{DEST}:{OUT_TAG}"
    # Clean gate: audit_breached must be False in the structured event.
    assert len(reporter.operations) == 1
    assert reporter.operations[0].audit_breached is False


def test_gate_without_sbom_formats_fails_the_op() -> None:
    # A scan gate needs an SBOM to evaluate; no formats => the op fails (not a silent skip).
    registry = _registry()
    report = _run(
        _policy(enforce="high"),
        registry,
        sbom_formats=[],
        vuln_evaluator=FakeVulnEvaluatorPort(sarif=SARIF_CLEAN),
    )

    assert report.totals.imported == 0
    assert report.totals.failed == 1
    # Nothing promoted; staging cleaned up.
    assert (f"{DEST}:{STAGING}", f"{DEST}:{OUT_TAG}") not in registry.copied
    assert f"{DEST}:{STAGING}" in registry.deleted


def test_evaluator_failure_fails_op_and_cleans_staging() -> None:
    # A fail-closed evaluator error must fail the op and leave no orphan staging tag.
    registry = _registry()
    report = _run(
        _policy(enforce="high"),
        registry,
        vuln_evaluator=FakeVulnEvaluatorPort(fail=True),
    )

    assert report.totals.imported == 0
    assert report.totals.failed == 1
    assert (f"{DEST}:{STAGING}", f"{DEST}:{OUT_TAG}") not in registry.copied
    assert f"{DEST}:{STAGING}" in registry.deleted


def test_gate_without_evaluator_raises_config_error() -> None:
    registry = _registry()
    with pytest.raises(ConfigError):
        _run(_policy(enforce="high"), registry, vuln_evaluator=None)


def test_no_gate_is_unchanged_no_staging() -> None:
    # Regression: a policy without a gate must not stage, scan, or change behavior.
    registry = _registry()
    report = _run(_policy(), registry, vuln_evaluator=FakeVulnEvaluatorPort(sarif=SARIF_CRITICAL))

    assert report.totals.imported == 1
    # Direct copy to the public out_tag; no staging tag anywhere.
    assert (f"{SRC}:{OUT_TAG}", f"{DEST}:{OUT_TAG}") in registry.copied
    assert all(STAGING not in dst for _src, dst in registry.copied)
    assert all(STAGING not in ref for ref in registry.deleted)
    assert all(STAGING not in ref for ref, _ann in registry.annotated)
    # No SARIF referrer (no gate => no scan).
    out_digest = registry.annotate(f"{DEST}:{OUT_TAG}", {})
    assert _scan_referrers(registry, f"{DEST}@{out_digest}") == []
