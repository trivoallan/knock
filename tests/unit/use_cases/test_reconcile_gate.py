"""The gate between reconcile's diff and its application (--plan-out / --apply-plan)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from knock.adapters.local_archiver import LocalArchiver
from knock.config import CACertSource, PackageMirror, RegistryConfig
from knock.domain.gate import Gate, PlannedOperation, ReconcilePlan
from knock.domain.mirror_policy import MirrorPolicy, parse_mirror_policy
from knock.ports.registry import ImageInfo
from knock.use_cases.report import Operation, RunReport
from tests.fakes.attestor import FakeAttestor
from tests.fakes.image_builder import FakeImageBuilder
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter
from tests.fakes.source import FakeSourcePort

NOW = datetime(2026, 6, 11, tzinfo=UTC)
OLD = NOW - timedelta(days=30)  # past the 7-day stability window
SRC = "docker.io/library/busybox"
DEST = "reg.local/demo/busybox"
BASE = "org.opencontainers.image.base.digest"

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
      destinations: [{ project: demo, repository: busybox }]
"""


def _policy(admit: bool = False) -> MirrorPolicy:
    return parse_mirror_policy(POLICY.replace("{admit}", str(admit).lower()))


def _registry(mirror: dict[str, str] | None = None) -> FakeRegistryPort:
    """Source tags 1.36.0 (sha256:s36) and 1.37.0 (sha256:s37); `mirror` maps a placed
    destination tag to the source digest recorded in its stamp."""
    mirror = mirror or {}
    infos = {
        f"{SRC}:1.36.0": ImageInfo(digest="sha256:s36", created=OLD, annotations={}),
        f"{SRC}:1.37.0": ImageInfo(digest="sha256:s37", created=OLD, annotations={}),
    }
    for tag, base in mirror.items():
        infos[f"{DEST}:{tag}"] = ImageInfo(
            digest=f"sha256:placed-{tag}", created=OLD, annotations={BASE: base}
        )
    return FakeRegistryPort(tags={SRC: ["1.36.0", "1.37.0"], DEST: list(mirror)}, infos=infos)


def _run(policy: MirrorPolicy, registry: FakeRegistryPort, gate: Gate, **over: object) -> RunReport:
    from knock.use_cases.reconcile import reconcile_policies

    kwargs: dict[str, object] = dict(
        registry=registry,
        builder=FakeImageBuilder(),
        source=FakeSourcePort(),
        archiver=LocalArchiver(),
        roster={"local": RegistryConfig(host="reg.local")},
        ca_certs={"corp": CACertSource(pem="PEMDATA")},
        package_mirrors={"corp": PackageMirror(apt="https://mirror.corp")},
        build_platform="linux/amd64",
        now=NOW,
        label_prefix="io.knock",
        dry_run_tags=False,
        dry_run_deletions=False,
        reporter=FakeReporter(),
        gate=gate,
    )
    kwargs.update(over)
    return reconcile_policies([policy], **kwargs)  # type: ignore[arg-type]


def _entry(tag: str, digest: str, kind: str = "import") -> PlannedOperation:
    return PlannedOperation.model_validate(
        dict(
            policy="busybox",
            kind=kind,
            destination=DEST,
            tag=tag,
            source=SRC,
            sourceTag=tag,
            sourceDigest=digest,
        )
    )


def _approve(*entries: PlannedOperation) -> Gate:
    return Gate.from_plan(ReconcilePlan(operations=list(entries)))


def _ops(report: RunReport) -> list[Operation]:
    return [op for v in report.policies[0].targets[0].variants for op in v.operations]


def test_plan_out_records_every_import_and_places_nothing() -> None:
    registry, gate = _registry(), Gate()
    _run(_policy(), registry, gate, dry_run_tags=True, dry_run_deletions=True)
    assert gate.planned == [_entry("1.36.0", "sha256:s36"), _entry("1.37.0", "sha256:s37")]
    assert registry.copied == [] and registry.annotated == []


def test_plan_out_marks_a_transform_change_as_rebuild() -> None:
    policy = parse_mirror_policy(Path("docs/examples/hardened/redis.yml").read_text())
    src, dest = "docker.io/library/redis", "reg.local/hardened/redis"
    registry = FakeRegistryPort(
        tags={src: ["7.2.5"], dest: ["7.2.5"]},
        infos={
            f"{src}:7.2.5": ImageInfo(digest="sha256:same", created=OLD, annotations={}),
            # upstream unchanged; the recorded transform version is not the policy's
            f"{dest}:7.2.5": ImageInfo(
                digest="sha256:p5",
                created=OLD,
                annotations={BASE: "sha256:same", "io.knock.transform.version": "stale"},
            ),
        },
    )
    gate = Gate()
    _run(policy, registry, gate, dry_run_tags=True, dry_run_deletions=True)
    assert [(op.tag, op.kind, op.source_digest) for op in gate.planned] == [
        ("7.2.5", "rebuild", "sha256:same")
    ]


def test_plan_out_marks_a_settled_upstream_move_as_update() -> None:
    gate = Gate()
    registry = _registry({"1.36.0": "sha256:old", "1.37.0": "sha256:s37"})
    _run(_policy(), registry, gate, dry_run_tags=True, dry_run_deletions=True)
    assert gate.planned == [_entry("1.36.0", "sha256:s36", "update")]


def test_apply_plan_places_only_approved_operations() -> None:
    registry = _registry()
    report = _run(_policy(), registry, _approve(_entry("1.36.0", "sha256:s36")))
    assert registry.copied[0] == (f"{SRC}@sha256:s36", f"{DEST}:1.36.0")
    assert not any(dst == f"{DEST}:1.37.0" for _src, dst in registry.copied)
    kinds = {op.out_tag: op.kind for op in _ops(report)}
    assert kinds["1.36.0"] == "imported"
    assert kinds["1.37.0"] == "withheld"
    assert report.totals.withheld == 1
    assert report.status == "ok"  # a refusal is a verdict, not a failure


def test_refused_import_does_not_move_the_alias() -> None:
    registry = _registry()
    _run(_policy(), registry, _approve(_entry("1.36.0", "sha256:s36")))
    # alias "1" targets the highest tag, 1.37.0, which was withheld: never written.
    assert not any(dst == f"{DEST}:1" for _src, dst in registry.copied)


def test_upstream_moved_since_the_plan_withholds() -> None:
    registry = _registry()
    report = _run(_policy(), registry, _approve(_entry("1.36.0", "sha256:evaluated-earlier")))
    assert registry.copied == []
    assert {op.kind for op in _ops(report)} == {"withheld"}


def test_refused_update_keeps_the_version_in_service() -> None:
    registry = _registry({"1.36.0": "sha256:old", "1.37.0": "sha256:s37"})
    report = _run(_policy(), registry, _approve())
    assert not any(dst == f"{DEST}:1.36.0" for _src, dst in registry.copied)
    assert registry.deleted == []
    kinds = {op.out_tag: op.kind for op in _ops(report)}
    assert kinds["1.36.0"] == "withheld"
    assert kinds["1.37.0"] == "skipped"


def test_admitted_policy_signs_only_approved_placements() -> None:
    attestor = FakeAttestor()
    _run(
        _policy(admit=True),
        _registry(),
        _approve(_entry("1.36.0", "sha256:s36")),
        attestor=attestor,
    )
    assert len(attestor.signed) == 1
    assert attestor.signed[0] == attestor.attested[0][0]


def test_backfill_under_the_gate_attests_without_signing() -> None:
    # Placed and current, but unattested: the backfill runs; this round judged nothing.
    attestor = FakeAttestor()
    registry = _registry({"1.36.0": "sha256:s36", "1.37.0": "sha256:s37"})
    _run(_policy(admit=True), registry, _approve(), attestor=attestor)
    assert len(attestor.attested) == 2
    assert attestor.signed == []
