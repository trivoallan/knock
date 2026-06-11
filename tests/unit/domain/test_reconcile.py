from __future__ import annotations

from datetime import UTC, datetime, timedelta

from houba.domain.expand import VariantPlan
from houba.domain.reconcile import (
    MirrorArtifact,
    SourceArtifact,
    VariantReconcile,
    _classify,
    reconcile_variant,
)

NOW = datetime(2026, 6, 11, tzinfo=UTC)
GRACE = timedelta(days=7)


def _src(digest: str, days_ago: int) -> SourceArtifact:
    return SourceArtifact(digest=digest, pushed_at=NOW - timedelta(days=days_ago))


def _plan(name: str, suffix: str, tags: list[str], aliases: dict[str, str]) -> VariantPlan:
    return VariantPlan(name=name, suffix=suffix, transform=[], tags=tags, aliases=aliases)


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


def test_reconcile_variant_import_and_update_with_suffix() -> None:
    plan = _plan(
        "fips",
        "-fips",
        tags=["7.2.0", "7.3.0"],
        aliases={"7.2": "7.2.0", "latest": "7.3.0"},
    )
    source = {
        "7.2.0": _src("sha256:a", 30),  # unchanged vs mirror → skip
        "7.3.0": _src("sha256:new", 30),  # new (absent from mirror) → import
    }
    mirror = {
        "7.2.0-fips": MirrorArtifact(base_digest="sha256:a"),  # output tag carries suffix
    }
    got = reconcile_variant(plan, source, mirror, NOW, GRACE)
    assert isinstance(got, VariantReconcile)
    assert got.variant == "fips"
    assert got.to_import == ["7.3.0-fips"]  # suffix applied
    assert got.to_update == []
    # suffix applied on both alias name and target
    assert got.aliases == {"7.2-fips": "7.2.0-fips", "latest-fips": "7.3.0-fips"}


def test_reconcile_variant_update_when_base_digest_changed() -> None:
    plan = _plan("standard", "", tags=["1.0.0"], aliases={})
    source = {"1.0.0": _src("sha256:b", 10)}  # changed, stable
    mirror = {"1.0.0": MirrorArtifact(base_digest="sha256:a")}
    got = reconcile_variant(plan, source, mirror, NOW, GRACE)
    assert got.to_update == ["1.0.0"]
    assert got.to_import == []


def test_reconcile_variant_empty_suffix_passthrough() -> None:
    plan = _plan("standard", "", tags=["2.0.0"], aliases={"2": "2.0.0"})
    source = {"2.0.0": _src("sha256:x", 30)}
    got = reconcile_variant(plan, source, {}, NOW, GRACE)
    assert got.to_import == ["2.0.0"]
    assert got.aliases == {"2": "2.0.0"}
