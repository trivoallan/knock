from __future__ import annotations

from datetime import UTC, datetime

from houba.ports.registry import ImageInfo
from houba.use_cases.reconcile import to_mirror_artifact, to_source_artifact

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
