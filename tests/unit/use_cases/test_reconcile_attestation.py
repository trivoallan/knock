from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from houba.config import CACertSource, PackageMirror, RegistryConfig
from houba.domain.attestation import PREDICATE_TYPE
from houba.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from houba.ports.registry import ImageInfo
from houba.use_cases.reconcile import reconcile_policies
from houba.use_cases.report import RunReport
from tests.fakes.attestor import FakeAttestor
from tests.fakes.image_builder import FakeImageBuilder
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter

NOW = datetime(2026, 6, 11, tzinfo=UTC)


def _hardened_policy() -> MirrorPolicy:
    return parse_mirror_policy(Path("docs/examples/hardened/redis.yml").read_text())


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
        attest_builder_id="https://houba.example/builders/main",
    )
    kwargs.update(over)
    return reconcile_policies([policy], **kwargs)  # type: ignore[arg-type]


def _hardened_registry() -> FakeRegistryPort:
    src = "docker.io/library/redis"
    return FakeRegistryPort(
        tags={src: ["7.2.5"], "reg.local/hardened/redis": []},
        infos={f"{src}:7.2.5": ImageInfo(digest="sha256:src", created=NOW, annotations={})},
    )


def test_rebuild_attests_with_transform_predicate() -> None:
    registry = _hardened_registry()
    builder = FakeImageBuilder()
    attestor = FakeAttestor()
    report = _run(_hardened_policy(), registry, builder=builder, attestor=attestor)

    assert report.totals.imported == 1
    assert builder.requests[0].provenance is True
    assert len(attestor.attested) == 1
    subject_ref, statement = attestor.attested[0]
    out_digest = registry.annotate(
        "reg.local/hardened/redis:7.2.5", {}
    )  # deterministic fake digest
    assert subject_ref == f"reg.local/hardened/redis@{out_digest}"
    assert statement["predicateType"] == PREDICATE_TYPE
    pred = statement["predicate"]
    assert pred["policy"] == "redis-hardened"
    assert pred["import"] == "v7"
    assert pred["source"] == "docker.io/library/redis"
    assert pred["source_digest"] == "sha256:src"
    assert pred["builder_id"] == "https://houba.example/builders/main"
    assert [s["name"] for s in pred["steps"]] == ["injectCA", "rewritePackageSources"]


def test_copy_path_is_not_attested_even_with_attestor() -> None:
    src = "docker.io/library/busybox"
    registry = FakeRegistryPort(
        tags={src: ["1.36.0"], "reg.local/demo/busybox": []},
        infos={f"{src}:1.36.0": ImageInfo(digest="sha256:s", created=NOW, annotations={})},
    )
    builder = FakeImageBuilder()
    attestor = FakeAttestor()
    _run(_copy_policy(), registry, builder=builder, attestor=attestor)
    assert attestor.attested == []
    assert builder.requests == []


def test_no_attestor_means_no_provenance() -> None:
    registry = _hardened_registry()
    builder = FakeImageBuilder()
    _run(_hardened_policy(), registry, builder=builder, attestor=None)
    assert builder.requests[0].provenance is False


def test_dry_run_does_not_attest() -> None:
    registry = _hardened_registry()
    attestor = FakeAttestor()
    _run(_hardened_policy(), registry, attestor=attestor, dry_run_tags=True, dry_run_deletions=True)
    assert attestor.attested == []


def test_attestation_failure_fails_the_operation() -> None:
    registry = _hardened_registry()
    report = _run(_hardened_policy(), registry, attestor=FakeAttestor(fail=True))
    assert report.status == "failed"
    op = report.policies[0].targets[0].variants[0].operations[0]
    assert op.error is not None
    assert op.error.type == "CosignError"
    assert op.error.exit_code == 2
