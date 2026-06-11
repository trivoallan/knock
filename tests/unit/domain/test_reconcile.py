from __future__ import annotations

from datetime import UTC, datetime, timedelta

from houba.domain.reconcile import (
    MirrorArtifact,
    SourceArtifact,
    _classify,
)

NOW = datetime(2026, 6, 11, tzinfo=UTC)
GRACE = timedelta(days=7)


def _src(digest: str, days_ago: int) -> SourceArtifact:
    return SourceArtifact(digest=digest, pushed_at=NOW - timedelta(days=days_ago))


def test_classify_import_when_absent_from_mirror() -> None:
    assert _classify(_src("sha256:a", 30), None, NOW, GRACE) == "import"


def test_classify_skip_when_base_digest_unchanged() -> None:
    src = _src("sha256:a", 30)
    mir = MirrorArtifact(base_digest="sha256:a")
    assert _classify(src, mir, NOW, GRACE) == "skip"


def test_classify_update_when_changed_and_stable() -> None:
    src = _src("sha256:b", 10)  # source moved 10 days ago → past grace
    mir = MirrorArtifact(base_digest="sha256:a")
    assert _classify(src, mir, NOW, GRACE) == "update"


def test_classify_skip_when_changed_but_within_grace() -> None:
    src = _src("sha256:b", 3)  # source moved 3 days ago → within 7-day grace
    mir = MirrorArtifact(base_digest="sha256:a")
    assert _classify(src, mir, NOW, GRACE) == "skip"


def test_classify_update_exactly_at_grace_boundary() -> None:
    src = SourceArtifact(digest="sha256:b", pushed_at=NOW - GRACE)  # exactly 7 days
    mir = MirrorArtifact(base_digest="sha256:a")
    assert _classify(src, mir, NOW, GRACE) == "update"
