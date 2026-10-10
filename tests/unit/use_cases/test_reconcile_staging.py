"""Rebuilt images are held in a staging registry instead of being placed (--stage-to)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from knock.adapters.local_archiver import LocalArchiver
from knock.config import RegistryConfig
from knock.domain.gate import Gate, ReconcilePlan
from knock.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from knock.errors import ConfigError
from knock.ports.registry import ImageInfo
from knock.use_cases.reconcile import reconcile_policies
from knock.use_cases.reconcile_registry import Staging
from knock.use_cases.report import Operation, RunReport
from tests.fakes.attestor import FakeAttestor
from tests.fakes.image_builder import FakeImageBuilder
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter
from tests.fakes.sbom_generator import FakeSbomGenerator
from tests.fakes.source import FakeSourcePort

NOW = datetime(2026, 6, 11, tzinfo=UTC)
OLD = NOW - timedelta(days=30)
SRC = "docker.io/library/busybox"
DEST = "reg.local/demo/busybox"
STAGED = "stage.local/demo/busybox"
BASE = "org.opencontainers.image.base.digest"
ROSTER = {
    "local": RegistryConfig(host="reg.local"),
    "stage": RegistryConfig(host="stage.local", tls_verify=False),
}

POLICY = """
apiVersion: knock.io/v1alpha1
kind: MirrorPolicy
metadata: { name: busybox }
spec:
  artifactType: image
  admit: {admit}
  source: { registry: docker.io, repository: library/busybox }
  imports:
    - name: stable
      tags: { includeRegex: "^1\\\\.3[67]\\\\.0$", aliases: ["1"] }
      {transform}
      destinations: [{ registry: local, project: demo, repository: busybox }]
"""
TRANSFORM = "transform: [ { setTimezone: { zone: UTC } } ]"


def _policy(*, admit: bool = False, transform: bool = True) -> MirrorPolicy:
    text = POLICY.replace("{admit}", str(admit).lower())
    return parse_mirror_policy(text.replace("{transform}", TRANSFORM if transform else ""))


def _registry(mirror: dict[str, dict[str, str]] | None = None) -> FakeRegistryPort:
    """Source tags 1.36.0 and 1.37.0; `mirror` maps a placed tag to its stamp annotations."""
    mirror = mirror or {}
    infos = {
        f"{SRC}:1.36.0": ImageInfo(digest="sha256:s36", created=OLD, annotations={}),
        f"{SRC}:1.37.0": ImageInfo(digest="sha256:s37", created=OLD, annotations={}),
    }
    for tag, stamp in mirror.items():
        infos[f"{DEST}:{tag}"] = ImageInfo(
            digest=f"sha256:placed-{tag}", created=OLD, annotations=stamp
        )
    return FakeRegistryPort(tags={SRC: ["1.36.0", "1.37.0"], DEST: list(mirror)}, infos=infos)


def _run(policy: MirrorPolicy, registry: FakeRegistryPort, **over: object) -> RunReport:
    kwargs: dict[str, object] = dict(
        registry=registry,
        builder=FakeImageBuilder(),
        source=FakeSourcePort(),
        archiver=LocalArchiver(),
        roster=ROSTER,
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


def _approved(policy: MirrorPolicy, registry: FakeRegistryPort) -> Gate:
    """Plan, approve everything: the gate a staged run goes through."""
    recording = Gate()
    _run(policy, registry, gate=recording, dry_run_tags=True, dry_run_deletions=True)
    return Gate.from_plan(ReconcilePlan(operations=recording.planned))


def _staging() -> Staging:
    return Staging(config=ROSTER["stage"])


def _ops(report: RunReport) -> list[Operation]:
    return [op for v in report.policies[0].targets[0].variants for op in v.operations]


def test_an_import_with_transforms_is_staged_and_the_destination_untouched() -> None:
    policy, registry, builder, staging = _policy(), _registry(), FakeImageBuilder(), _staging()
    report = _run(
        policy, registry, builder=builder, gate=_approved(policy, registry), staging=staging
    )

    assert [r.image_ref for r in builder.requests] == [f"{STAGED}:1.36.0", f"{STAGED}:1.37.0"]
    # the staging registry's own TLS setting reaches the push, not the destination's
    assert {r.tls_verify for r in builder.requests} == {False}
    assert all(ref.startswith(STAGED) for ref, _ in registry.annotated)
    assert not any(dst.startswith(DEST) for _src, dst in registry.copied)
    assert report.totals.staged == 2 and report.totals.imported == 0
    assert [op.kind for op in _ops(report)] == ["staged", "staged"]
    assert all(op.applied and op.out_digest for op in _ops(report))


def test_the_staged_entries_say_what_was_held_and_where_it_goes() -> None:
    policy, registry, staging = _policy(), _registry(), _staging()
    report = _run(policy, registry, gate=_approved(policy, registry), staging=staging)

    by_tag = {e.tag: e for e in staging.entries}
    assert set(by_tag) == {"1.36.0", "1.37.0"}
    e = by_tag["1.37.0"]
    assert (e.policy, e.import_name, e.variant, e.kind) == (
        "busybox",
        "stable",
        "default",
        "import",
    )
    assert (e.destination, e.staged) == (DEST, STAGED)
    assert (e.source, e.source_tag, e.source_digest) == (SRC, "1.37.0", "sha256:s37")
    out = {op.out_tag: op.out_digest for op in _ops(report)}
    assert e.staged_digest == out["1.37.0"]
    # the alias reconcile resolved onto the highest tag is recorded on that entry only
    assert e.aliases == ("1",)
    assert by_tag["1.36.0"].aliases == ()


def test_an_alias_does_not_move_onto_a_staged_tag() -> None:
    policy, registry = _policy(), _registry()
    report = _run(policy, registry, gate=_approved(policy, registry), staging=_staging())
    assert not any(dst == f"{DEST}:1" for _src, dst in registry.copied)
    assert "aliased" not in [op.kind for op in _ops(report)]


def test_a_rebuild_of_a_placed_tag_leaves_it_in_service() -> None:
    stale = {BASE: "sha256:s37", "io.knock.transform.version": "stale"}
    policy, registry, staging = _policy(), _registry({"1.37.0": stale}), _staging()
    builder = FakeImageBuilder()
    _run(policy, registry, builder=builder, gate=_approved(policy, registry), staging=staging)

    assert f"{STAGED}:1.37.0" in [r.image_ref for r in builder.requests]
    assert not any(ref.startswith(DEST) for ref, _ in registry.annotated)
    kinds = {e.tag: e.kind for e in staging.entries}
    assert kinds == {"1.36.0": "import", "1.37.0": "rebuild"}


def test_a_copy_path_import_is_placed_directly() -> None:
    policy, registry, staging = _policy(transform=False), _registry(), _staging()
    report = _run(policy, registry, gate=_approved(policy, registry), staging=staging)
    assert report.totals.imported == 2 and report.totals.staged == 0
    assert staging.entries == []
    assert (f"{SRC}@sha256:s37", f"{DEST}:1.37.0") in registry.copied


def test_a_staged_image_is_attested_and_not_signed() -> None:
    policy, registry, attestor = _policy(admit=True), _registry(), FakeAttestor()
    # planned with the attestor too: an admitting policy refuses to plan without a signer
    recording = Gate()
    _run(
        policy,
        registry,
        gate=recording,
        attestor=attestor,
        dry_run_tags=True,
        dry_run_deletions=True,
    )
    gate = Gate.from_plan(ReconcilePlan(operations=recording.planned))
    _run(policy, registry, gate=gate, attestor=attestor, staging=_staging())

    assert attestor.attested and all(s.startswith(f"{STAGED}@") for s, _ in attestor.attested)
    # admission is promote's last act, on the destination
    assert attestor.signed == []


def test_the_sbom_is_generated_and_attached_in_staging() -> None:
    policy, registry, sbom = _policy(), _registry(), FakeSbomGenerator()
    _run(
        policy,
        registry,
        gate=_approved(policy, registry),
        staging=_staging(),
        sbom_generator=sbom,
        sbom_formats=["spdx"],
    )
    assert sbom.calls and all(ref.startswith(f"{STAGED}@") for ref, _f, _t in sbom.calls)
    assert {tls for _r, _f, tls in sbom.calls} == {False}
    assert all(ref.startswith(f"{STAGED}@") for ref, *_ in registry.artifact_referrers)


def test_a_dry_run_stages_nothing() -> None:
    policy, registry, builder, staging = _policy(), _registry(), FakeImageBuilder(), _staging()
    _run(
        policy,
        registry,
        builder=builder,
        gate=_approved(policy, registry),
        staging=staging,
        dry_run_tags=True,
    )
    assert builder.requests == [] and staging.entries == []


def test_a_failed_build_has_no_entry_and_the_other_is_staged() -> None:
    policy, registry, staging = _policy(), _registry(), _staging()
    builder = FakeImageBuilder(fail_refs={f"{STAGED}:1.36.0"})
    report = _run(
        policy, registry, builder=builder, gate=_approved(policy, registry), staging=staging
    )
    assert [e.tag for e in staging.entries] == ["1.37.0"]
    assert report.totals.failed == 1 and report.totals.staged == 1


def test_an_attestation_failure_after_the_push_has_no_entry() -> None:
    policy, registry, staging = _policy(), _registry(), _staging()
    gate = _approved(policy, registry)
    report = _run(policy, registry, gate=gate, staging=staging, attestor=FakeAttestor(fail=True))
    assert staging.entries == []
    assert report.totals.failed == 2 and report.totals.staged == 0


def test_an_unpromoted_import_is_planned_again() -> None:
    policy, registry = _policy(), _registry()
    _run(policy, registry, gate=_approved(policy, registry), staging=_staging())
    again = Gate()
    _run(policy, registry, gate=again, dry_run_tags=True, dry_run_deletions=True)
    assert [(op.tag, op.kind) for op in again.planned] == [
        ("1.36.0", "import"),
        ("1.37.0", "import"),
    ]


def test_staging_in_a_destination_registry_is_refused_before_anything_is_built() -> None:
    policy, registry, builder = _policy(), _registry(), FakeImageBuilder()
    with pytest.raises(ConfigError, match="staging registry"):
        _run(policy, registry, builder=builder, staging=Staging(config=ROSTER["local"]))
    assert builder.requests == []
