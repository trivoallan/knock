from datetime import UTC, datetime

from houba.config import RegistryConfig
from houba.domain.deletion_mode import DeletionMode
from houba.domain.lifecycle import PENDING_DELETION_ARTIFACT_TYPE
from houba.domain.mirror_policy import parse_mirror_policy
from houba.ports.registry import ImageInfo, Referrer
from houba.use_cases.reconcile import reconcile_policies
from houba.use_cases.report import RunReport
from tests.fakes.image_builder import FakeImageBuilder
from tests.fakes.registry import FakeRegistryPort
from tests.fakes.reporter import FakeReporter

_NOW = datetime(2026, 6, 12, tzinfo=UTC)

_POLICY = """
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata:
  name: redis
spec:
  artifactType: image
  source:
    registry: docker.io
    repository: library/redis
  deletionMode: {mode}
  imports:
    - name: stable
      tags:
        includeRegex: "^7\\\\."
      destinations:
        - registry: harbor
          project: lib
          repository: redis
"""


def _roster() -> dict[str, RegistryConfig]:
    return {"harbor": RegistryConfig(host="harbor.corp")}


def _seed_registry(referrers: dict[str, list[Referrer]] | None = None) -> FakeRegistryPort:
    # source has 7.2.0; mirror has the desired 7.2.0 (stamped) plus obsolete 6.0.0 (stamped)
    stamped = {"org.opencontainers.image.base.digest": "sha256:s"}
    return FakeRegistryPort(
        tags={
            "docker.io/library/redis": ["7.2.0"],
            "harbor.corp/lib/redis": ["7.2.0", "6.0.0"],
        },
        infos={
            "docker.io/library/redis:7.2.0": ImageInfo(
                digest="sha256:s", created=_NOW, annotations={}
            ),
            "harbor.corp/lib/redis:7.2.0": ImageInfo(
                digest="sha256:s", created=_NOW, annotations=stamped
            ),
            "harbor.corp/lib/redis:6.0.0": ImageInfo(
                digest="sha256:old", created=_NOW, annotations=stamped
            ),
        },
        referrers=referrers,
    )


def _run(reg: FakeRegistryPort, mode: str, *, global_mode: DeletionMode) -> RunReport:
    return reconcile_policies(
        [parse_mirror_policy(_POLICY.format(mode=mode))],
        registry=reg,
        builder=FakeImageBuilder(),
        roster=_roster(),
        ca_certs={},
        package_mirrors={},
        build_platform="linux/amd64",
        now=_NOW,
        label_prefix="io.houba",
        dry_run_tags=False,
        dry_run_deletions=False,
        reporter=FakeReporter(),
        deletion_mode=global_mode,
    )


def test_mark_mode_marks_obsolete_tag_and_does_not_delete() -> None:
    reg = _seed_registry()
    _run(reg, "mark", global_mode=DeletionMode.purge)  # policy 'mark' overrides global 'purge'
    assert reg.deleted == []
    assert [m[0] for m in reg.marked] == ["harbor.corp/lib/redis:6.0.0"]
    assert reg.marked[0][1] == PENDING_DELETION_ARTIFACT_TYPE
    assert reg.marked[0][2]["io.houba.lifecycle.state"] == "pending-deletion"


def test_mark_mode_is_idempotent_for_already_marked_tag() -> None:
    existing = {
        "harbor.corp/lib/redis:6.0.0": [
            Referrer(
                digest="sha256:ref1",
                artifact_type=PENDING_DELETION_ARTIFACT_TYPE,
                annotations={},
                subject_tag="harbor.corp/lib/redis:6.0.0",
            )
        ]
    }
    reg = _seed_registry(referrers=existing)
    _run(reg, "mark", global_mode=DeletionMode.purge)
    assert reg.marked == []  # already marked → not re-marked
    assert reg.deleted == []


def test_purge_mode_deletes_obsolete_tag() -> None:
    reg = _seed_registry()
    _run(reg, "purge", global_mode=DeletionMode.mark)  # policy 'purge' overrides global 'mark'
    assert reg.deleted == ["harbor.corp/lib/redis:6.0.0"]
    assert reg.marked == []


def test_re_entered_tag_is_unmarked() -> None:
    # 7.2.0 is still desired but carries a stale pending-deletion mark → auto-unmark.
    existing = {
        "harbor.corp/lib/redis:7.2.0": [
            Referrer(
                digest="sha256:ref7",
                artifact_type=PENDING_DELETION_ARTIFACT_TYPE,
                annotations={},
                subject_tag="harbor.corp/lib/redis:7.2.0",
            )
        ]
    }
    reg = _seed_registry(referrers=existing)
    _run(reg, "mark", global_mode=DeletionMode.mark)
    assert reg.unmarked == ["harbor.corp/lib/redis@sha256:ref7"]
    # 6.0.0 (still obsolete) still gets marked; 7.2.0 only gets unmarked.
    assert [m[0] for m in reg.marked] == ["harbor.corp/lib/redis:6.0.0"]


def test_mark_failure_is_reported() -> None:
    reg = _seed_registry()
    reg._fail_put.add("harbor.corp/lib/redis:6.0.0")
    report = _run(reg, "mark", global_mode=DeletionMode.purge)
    assert reg.marked == []  # put_referrer raised before journaling
    assert report.totals.failed == 1
    assert report.totals.marked == 0  # a failed mark is not counted as marked
    assert report.status == "partial"  # the 7.2.0 import succeeded; the mark failed
