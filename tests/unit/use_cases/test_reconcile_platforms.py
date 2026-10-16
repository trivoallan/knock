"""Multi-platform rebuild: one build per index, refusal of a source lacking a platform,
platform drift, and per-platform SBOMs (change rebuild-multi-platform)."""

from __future__ import annotations

from datetime import UTC, datetime

from knock.adapters.local_archiver import LocalArchiver
from knock.config import RegistryConfig
from knock.domain.gate import Gate
from knock.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from knock.ports.registry import ImageInfo, Referrer
from knock.use_cases.reconcile import reconcile_policies
from knock.use_cases.report import RunReport
from tests.fakes.image_builder import FakeImageBuilder
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter
from tests.fakes.sbom_generator import FakeSbomGenerator
from tests.fakes.source import FakeSourcePort

NOW = datetime(2026, 10, 16, tzinfo=UTC)
SRC = "docker.io/library/python"
DEST = "reg.local/base/python"
SPDX = "application/spdx+json"
AMD = ("linux/amd64",)
BOTH = ("linux/amd64", "linux/arm64")
TV = "io.knock.transform.version"


def _policy(platforms: str | None = "[linux/amd64, linux/arm64]") -> MirrorPolicy:
    line = f"      platforms: {platforms}\n" if platforms else ""
    return parse_mirror_policy(
        f"""
apiVersion: knock.io/v1alpha1
kind: MirrorPolicy
metadata: {{ name: python }}
spec:
  artifactType: image
  source: {{ registry: docker.io, repository: library/python }}
  imports:
    - name: alpine
      tags: {{ names: ["3.13-alpine"], semverOnly: false }}
      transform:
        - setTimezone: {{ zone: Europe/Paris }}
{line}      destinations: [{{ project: base, repository: python }}]
"""
    )


def _registry(
    *,
    source_platforms: tuple[str, ...] = BOTH,
    placed: tuple[str, ...] | None = None,
    referrers: list[Referrer] | None = None,
    tv: str | None = None,
) -> FakeRegistryPort:
    infos = {
        f"{SRC}:3.13-alpine": ImageInfo(
            digest="sha256:src", created=NOW, annotations={}, platforms=source_platforms
        )
    }
    tags: dict[str, list[str]] = {SRC: ["3.13-alpine"], DEST: []}
    if placed is not None:
        tags[DEST] = ["3.13-alpine"]
        ann = {"org.opencontainers.image.base.digest": "sha256:src"}
        if tv:
            ann[TV] = tv
        infos[f"{DEST}:3.13-alpine"] = ImageInfo(
            digest="sha256:placed", created=NOW, annotations=ann, platforms=placed
        )
    return FakeRegistryPort(
        tags=tags, infos=infos, referrers={f"{DEST}:3.13-alpine": referrers or []}
    )


def _run(
    policy: MirrorPolicy, registry: FakeRegistryPort, builder: FakeImageBuilder, **over: object
) -> RunReport:
    kwargs: dict[str, object] = dict(
        registry=registry,
        builder=builder,
        source=FakeSourcePort(),
        archiver=LocalArchiver(),
        roster={"local": RegistryConfig(host="reg.local")},
        ca_certs={},
        package_mirrors={},
        build_platform="linux/amd64",
        now=NOW,
        label_prefix="io.knock",
        dry_run_tags=False,
        dry_run_deletions=False,
        reporter=FakeReporter(),
    )
    kwargs.update(over)
    return reconcile_policies([policy], **kwargs)  # type: ignore[arg-type]


def _current_tv(registry: FakeRegistryPort) -> str:
    # The transform version knock stamps on a fresh build of this policy.
    builder = FakeImageBuilder()
    _run(_policy(), registry, builder)
    return next(v for _r, ann in registry.annotated for k, v in ann.items() if k == TV)


def test_two_platforms_are_built_in_one_request_in_policy_order() -> None:
    builder = FakeImageBuilder()
    report = _run(_policy(), _registry(), builder)
    assert report.totals.imported == 1
    assert [r.platforms for r in builder.requests] == [BOTH]


def test_no_platforms_builds_the_configured_single_platform() -> None:
    builder = FakeImageBuilder()
    _run(_policy(None), _registry(), builder, build_platform="linux/arm64")
    assert [r.platforms for r in builder.requests] == [("linux/arm64",)]


def test_a_source_lacking_arm64_is_refused_before_any_build() -> None:
    builder = FakeImageBuilder()
    reporter = FakeReporter()
    report = _run(_policy(), _registry(source_platforms=AMD), builder, reporter=reporter)
    assert builder.requests == []
    assert report.status == "failed"
    [op] = report.policies[0].targets[0].variants[0].operations
    assert op.error is not None
    assert op.error.type == "PlatformUnavailableError"
    assert "linux/arm64" in op.error.message
    assert op.error.exit_code == 1


def test_a_refused_tag_is_absent_from_the_plan() -> None:
    gate = Gate()
    _run(
        _policy(),
        _registry(source_platforms=AMD),
        FakeImageBuilder(),
        gate=gate,
        dry_run_tags=True,
        dry_run_deletions=True,
    )
    assert gate.planned == []


def test_adding_arm64_rebuilds_a_placed_amd64_tag() -> None:
    tv = _current_tv(_registry())
    builder = FakeImageBuilder()
    report = _run(_policy(), _registry(placed=AMD, tv=tv), builder)
    assert report.totals.updated == 1
    assert [r.platforms for r in builder.requests] == [BOTH]


def test_upgrade_with_unchanged_platforms_rebuilds_nothing() -> None:
    tv = _current_tv(_registry())
    builder = FakeImageBuilder()
    _run(_policy(None), _registry(placed=AMD, tv=tv), builder)
    assert builder.requests == []


def test_one_sbom_per_format_and_platform_on_the_index() -> None:
    registry = _registry()
    gen = FakeSbomGenerator()
    _run(_policy(), registry, FakeImageBuilder(), sbom_generator=gen, sbom_formats=["spdx-json"])
    out_digest = registry.annotate(f"{DEST}:3.13-alpine", {})
    subject = f"{DEST}@{out_digest}"
    platforms = [
        r[4].get("io.knock.sbom.platform")
        for r in registry.artifact_referrers
        if r[0] == subject and r[1] == SPDX
    ]
    assert platforms == list(BOTH)
    assert gen.platforms == list(BOTH)


def test_missing_arm64_sbom_is_backfilled_on_the_kept_index() -> None:
    tv = _current_tv(_registry())
    have = [Referrer("sha256:r1", SPDX, {"io.knock.sbom.platform": "linux/amd64"}, "3.13-alpine")]
    registry = _registry(placed=BOTH, referrers=have, tv=tv)
    gen = FakeSbomGenerator()
    report = _run(
        _policy(), registry, FakeImageBuilder(), sbom_generator=gen, sbom_formats=["spdx-json"]
    )
    assert report.totals.sbom == 1
    assert gen.platforms == ["linux/arm64"]


def test_an_older_single_platform_image_stays_covered() -> None:
    tv = _current_tv(_registry())
    have = [Referrer("sha256:r1", SPDX, {}, "3.13-alpine")]
    registry = _registry(source_platforms=AMD, placed=AMD, referrers=have, tv=tv)
    gen = FakeSbomGenerator()
    report = _run(
        _policy(None), registry, FakeImageBuilder(), sbom_generator=gen, sbom_formats=["spdx-json"]
    )
    assert report.totals.sbom == 0
    assert gen.calls == []


def test_a_copied_multi_arch_index_is_not_rescanned() -> None:
    copy = parse_mirror_policy(
        """
apiVersion: knock.io/v1alpha1
kind: MirrorPolicy
metadata: { name: python-copy }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/python }
  imports:
    - name: alpine
      tags: { names: ["3.13-alpine"], semverOnly: false }
      destinations: [{ project: base, repository: python }]
"""
    )
    have = [Referrer("sha256:r1", SPDX, {}, "3.13-alpine")]
    registry = _registry(placed=BOTH, referrers=have)
    gen = FakeSbomGenerator()
    report = _run(
        copy, registry, FakeImageBuilder(), sbom_generator=gen, sbom_formats=["spdx-json"]
    )
    assert report.totals.sbom == 0
    assert gen.calls == []
