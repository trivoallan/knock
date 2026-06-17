from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from houba.config import CACertSource, PackageMirror, RegistryConfig
from houba.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from houba.ports.registry import ImageInfo
from houba.use_cases.reconcile import reconcile_policies
from houba.use_cases.report import RunReport
from tests.fakes.attestor import FakeAttestor
from tests.fakes.image_builder import FakeImageBuilder
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter
from tests.fakes.sbom_generator import FAKE_SYFT_VERSION, FakeSbomGenerator

NOW = datetime(2026, 6, 17, tzinfo=UTC)

SPDX = "application/spdx+json"
CYCLONEDX = "application/vnd.cyclonedx+json"

SPDX_PREDICATE = "https://spdx.dev/Document"
CYCLONEDX_PREDICATE = "https://cyclonedx.org/bom"
SBOM_PREDICATES = {SPDX_PREDICATE, CYCLONEDX_PREDICATE}


def _sbom_attestations(attestor: FakeAttestor) -> list[tuple[str, dict]]:
    # attestor.attested journals (subject_ref, statement); keep only SBOM-typed ones
    # (the transform attestation, signed on the same digest, is filtered out).
    return [
        (ref, st) for ref, st in attestor.attested if st.get("predicateType") in SBOM_PREDICATES
    ]


def _copy_policy() -> MirrorPolicy:
    return parse_mirror_policy(
        """
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata: { name: busybox-copy }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/busybox }
  imports:
    - name: stable
      tags: { includeRegex: "^1\\\\.36\\\\.0$" }
      destinations: [{ project: demo, repository: busybox }]
"""
    )


def _hardened_policy() -> MirrorPolicy:
    return parse_mirror_policy(Path("docs/examples/hardened/redis.yml").read_text())


def _copy_registry() -> FakeRegistryPort:
    src = "docker.io/library/busybox"
    return FakeRegistryPort(
        tags={src: ["1.36.0"], "reg.local/demo/busybox": []},
        infos={f"{src}:1.36.0": ImageInfo(digest="sha256:bbsrc", created=NOW, annotations={})},
    )


def _hardened_registry() -> FakeRegistryPort:
    src = "docker.io/library/redis"
    return FakeRegistryPort(
        tags={src: ["7.2.5"], "reg.local/hardened/redis": []},
        infos={f"{src}:7.2.5": ImageInfo(digest="sha256:src", created=NOW, annotations={})},
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
    )
    kwargs.update(over)
    return reconcile_policies([policy], **kwargs)  # type: ignore[arg-type]


def _sbom_referrers(registry: FakeRegistryPort, subject: str) -> list[tuple[str, str]]:
    # artifact_referrers entries: (image_ref, artifact_type, media_type, blob, annotations)
    return [
        (r[1], r[2])
        for r in registry.artifact_referrers
        if r[0] == subject and r[1] in (SPDX, CYCLONEDX)
    ]


def test_copy_path_attaches_one_sbom_referrer_per_format() -> None:
    registry = _copy_registry()
    gen = FakeSbomGenerator()
    report = _run(
        _copy_policy(),
        registry,
        sbom_generator=gen,
        sbom_formats=["spdx-json", "cyclonedx-json"],
    )

    assert report.totals.imported == 1
    out_digest = registry.annotate("reg.local/demo/busybox:1.36.0", {})  # deterministic fake digest
    subject = f"reg.local/demo/busybox@{out_digest}"
    refs = _sbom_referrers(registry, subject)
    assert {media for _, media in refs} == {SPDX, CYCLONEDX}
    assert {art for art, _ in refs} == {SPDX, CYCLONEDX}  # artifactType == media type
    assert gen.calls == [(subject, ("spdx-json", "cyclonedx-json"), True)]


def test_rebuild_path_also_attaches_sbom_referrer() -> None:
    registry = _hardened_registry()
    report = _run(
        _hardened_policy(),
        registry,
        sbom_generator=FakeSbomGenerator(),
        sbom_formats=["spdx-json"],
    )

    assert report.totals.imported == 1
    out_digest = registry.annotate("reg.local/hardened/redis:7.2.5", {})
    subject = f"reg.local/hardened/redis@{out_digest}"
    assert _sbom_referrers(registry, subject) == [(SPDX, SPDX)]


def test_sbom_generation_failure_fails_the_op() -> None:
    registry = _copy_registry()
    report = _run(
        _copy_policy(),
        registry,
        sbom_generator=FakeSbomGenerator(fail=True),
        sbom_formats=["spdx-json"],
    )

    assert report.totals.imported == 0
    assert report.totals.failed == 1
    assert report.status != "ok"


def test_sbom_referrer_records_tool_version() -> None:
    registry = _copy_registry()
    _run(_copy_policy(), registry, sbom_generator=FakeSbomGenerator(), sbom_formats=["spdx-json"])

    out_digest = registry.annotate("reg.local/demo/busybox:1.36.0", {})
    subject = f"reg.local/demo/busybox@{out_digest}"
    # artifact_referrers entries: (image_ref, artifact_type, media_type, blob, annotations)
    ann = next(r[4] for r in registry.artifact_referrers if r[0] == subject)
    assert ann.get("io.houba.sbom.tool.version") == FAKE_SYFT_VERSION


def test_no_formats_means_no_sbom_calls() -> None:
    registry = _copy_registry()
    gen = FakeSbomGenerator()
    report = _run(_copy_policy(), registry, sbom_generator=gen)  # sbom_formats omitted

    assert report.totals.imported == 1
    assert gen.calls == []
    assert registry.artifact_referrers == []


def test_signs_one_sbom_attestation_per_format() -> None:
    registry = _copy_registry()
    attestor = FakeAttestor()
    report = _run(
        _copy_policy(),
        registry,
        sbom_generator=FakeSbomGenerator(),
        sbom_formats=["spdx-json", "cyclonedx-json"],
        attestor=attestor,
    )

    assert report.totals.imported == 1
    out_digest = registry.annotate("reg.local/demo/busybox:1.36.0", {})
    subject = f"reg.local/demo/busybox@{out_digest}"
    sboms = _sbom_attestations(attestor)
    assert {st["predicateType"] for _, st in sboms} == SBOM_PREDICATES
    assert all(ref == subject for ref, _ in sboms)
    assert all(st["subject"][0]["name"] == "reg.local/demo/busybox:1.36.0" for _, st in sboms)


def test_sbom_signing_is_gated_on_sbom_generation() -> None:
    # Attestor configured but no SBOM formats => transform is signed, SBOM is not.
    registry = _copy_registry()
    attestor = FakeAttestor()
    _run(_copy_policy(), registry, sbom_generator=FakeSbomGenerator(), attestor=attestor)

    assert _sbom_attestations(attestor) == []
    assert len(attestor.attested) == 1  # the transform attestation only
