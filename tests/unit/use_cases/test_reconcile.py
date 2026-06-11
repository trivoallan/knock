from __future__ import annotations

from datetime import UTC, datetime

import pytest

from houba.config import RegistryConfig
from houba.domain.mirror_policy import parse_mirror_policy
from houba.errors import PolicyValidationError
from houba.ports.registry import ImageInfo
from houba.use_cases.reconcile import (
    RunSummary,
    reconcile_policies,
    to_mirror_artifact,
    to_source_artifact,
)
from tests.fakes.registry import FakeRegistryPort

NOW = datetime(2026, 6, 11, tzinfo=UTC)
CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def test_to_source_artifact_uses_created() -> None:
    art = to_source_artifact(ImageInfo("sha256:a", CREATED, {}), now=NOW)
    assert art.digest == "sha256:a"
    assert art.pushed_at == CREATED


def test_to_source_artifact_falls_back_to_now_when_created_absent() -> None:
    art = to_source_artifact(ImageInfo("sha256:a", None, {}), now=NOW)
    assert art.pushed_at == NOW


def test_to_mirror_artifact_reads_base_digest() -> None:
    info = ImageInfo("sha256:m", CREATED, {"org.opencontainers.image.base.digest": "sha256:src"})
    art = to_mirror_artifact(info)
    assert art is not None
    assert art.base_digest == "sha256:src"


def test_to_mirror_artifact_none_when_unstamped() -> None:
    assert to_mirror_artifact(ImageInfo("sha256:m", CREATED, {})) is None


ROSTER = {"only": RegistryConfig(host="harbor.corp", username="robot", password="x")}

POLICY = parse_mirror_policy("""
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata: { name: redis, labels: { team: platform-data } }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/redis }
  imports:
    - name: v7
      tags: { includeRegex: "^7\\\\.", aliases: ["{major}.{minor}", "latest"] }
      destinations: [{ project: lib, repository: redis }]
""")


def _info(digest: str, ann: dict[str, str] | None = None) -> ImageInfo:
    return ImageInfo(digest=digest, created=CREATED, annotations=ann or {})


def test_reconcile_copies_new_tags_and_stamps() -> None:
    fake = FakeRegistryPort(
        tags={
            "docker.io/library/redis": ["7.2.0", "7.3.0"],
            "harbor.corp/lib/redis": [],
        },
        infos={
            "docker.io/library/redis:7.2.0": _info("sha256:a"),
            "docker.io/library/redis:7.3.0": _info("sha256:b"),
        },
    )
    summary = reconcile_policies(
        [POLICY],
        registry=fake,
        roster=ROSTER,
        now=NOW,
        label_prefix="io.houba",
        dry_run_tags=False,
        dry_run_deletions=False,
    )
    assert isinstance(summary, RunSummary)
    assert fake.logins == [("harbor.corp", "robot", True)]
    assert ("docker.io/library/redis:7.2.0", "harbor.corp/lib/redis:7.2.0") in fake.copied
    assert ("docker.io/library/redis:7.3.0", "harbor.corp/lib/redis:7.3.0") in fake.copied
    stamped = {ref: ann for ref, ann in fake.annotated}
    base_digest = stamped["harbor.corp/lib/redis:7.2.0"]["org.opencontainers.image.base.digest"]
    assert base_digest == "sha256:a"
    assert stamped["harbor.corp/lib/redis:7.2.0"]["io.houba.owner.team"] == "platform-data"
    assert ("harbor.corp/lib/redis:7.3.0", "harbor.corp/lib/redis:latest") in fake.copied
    assert summary.imported == 2


def test_reconcile_dry_run_tags_skips_mutations() -> None:
    fake = FakeRegistryPort(
        tags={"docker.io/library/redis": ["7.2.0"], "harbor.corp/lib/redis": []},
        infos={"docker.io/library/redis:7.2.0": _info("sha256:a")},
    )
    summary = reconcile_policies(
        [POLICY],
        registry=fake,
        roster=ROSTER,
        now=NOW,
        label_prefix="io.houba",
        dry_run_tags=True,
        dry_run_deletions=True,
    )
    assert fake.copied == []
    assert fake.annotated == []
    assert fake.deleted == []
    assert summary.imported == 1


def test_reconcile_collision_raises_before_mutation() -> None:
    policy = parse_mirror_policy("""
apiVersion: houba.io/v1alpha1
kind: MirrorPolicy
metadata: { name: redis }
spec:
  artifactType: image
  source: { registry: docker.io, repository: library/redis }
  imports:
    - name: a
      tags: { includeRegex: "^7\\\\.", aliases: ["latest"] }
      destinations: [{ project: lib, repository: redis }]
    - name: b
      tags: { includeRegex: "^8\\\\.", aliases: ["latest"] }
      destinations: [{ project: lib, repository: redis }]
""")
    fake = FakeRegistryPort(
        tags={"docker.io/library/redis": ["7.0.0", "8.0.0"], "harbor.corp/lib/redis": []},
        infos={
            "docker.io/library/redis:7.0.0": _info("sha256:a"),
            "docker.io/library/redis:8.0.0": _info("sha256:b"),
        },
    )
    with pytest.raises(PolicyValidationError, match="alias collision"):
        reconcile_policies(
            [policy],
            registry=fake,
            roster=ROSTER,
            now=NOW,
            label_prefix="io.houba",
            dry_run_tags=False,
            dry_run_deletions=False,
        )
    assert fake.copied == []  # fail-fast: nothing mutated
