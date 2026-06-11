from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from houba.domain.expand import ExpandedImport, VariantPlan
from houba.domain.reconcile import (
    ImportReconcile,
    MirrorArtifact,
    SourceArtifact,
    VariantReconcile,
    _classify,
    reconcile_import,
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


def _expanded(variants: list[VariantPlan]) -> ExpandedImport:
    return ExpandedImport(
        name="redis", destinations=None, platforms=None, archive=None, variants=variants
    )


def test_reconcile_import_runs_each_variant() -> None:
    exp = _expanded(
        [
            _plan("standard", "", ["7.2.0"], {"7.2": "7.2.0"}),
            _plan("fips", "-fips", ["7.2.0"], {"7.2": "7.2.0"}),
        ]
    )
    source = {"7.2.0": _src("sha256:a", 30)}
    got = reconcile_import(exp, source, {}, NOW, GRACE)
    assert isinstance(got, ImportReconcile)
    assert got.name == "redis"
    assert [v.variant for v in got.variants] == ["standard", "fips"]
    assert got.variants[0].to_import == ["7.2.0"]
    assert got.variants[1].to_import == ["7.2.0-fips"]


def test_reconcile_import_deletion_across_variants() -> None:
    # desired output across both variants: 7.2.0, 7.2 (std) + 7.2.0-fips, 7.2-fips (fips)
    exp = _expanded(
        [
            _plan("standard", "", ["7.2.0"], {"7.2": "7.2.0"}),
            _plan("fips", "-fips", ["7.2.0"], {"7.2": "7.2.0"}),
        ]
    )
    source = {"7.2.0": _src("sha256:a", 30)}
    mirror = {
        "7.2.0": MirrorArtifact(base_digest="sha256:a"),  # desired (std) → keep
        "7.2.0-fips": MirrorArtifact(base_digest="sha256:a"),  # desired (fips) → keep
        "6.0.0": MirrorArtifact(base_digest="sha256:old"),  # NOT desired → delete
        "6.0.0-fips": MirrorArtifact(base_digest="sha256:old"),  # NOT desired → delete
    }
    got = reconcile_import(exp, source, mirror, NOW, GRACE)
    assert sorted(got.to_delete) == ["6.0.0", "6.0.0-fips"]
    # the standard variant must NOT mark 7.2.0-fips (a sibling variant's tag) for deletion
    assert "7.2.0-fips" not in got.to_delete


def test_reconcile_import_aliases_are_not_deleted() -> None:
    exp = _expanded([_plan("standard", "", ["7.2.0"], {"7.2": "7.2.0", "latest": "7.2.0"})])
    source = {"7.2.0": _src("sha256:a", 30)}
    mirror = {
        "7.2": MirrorArtifact(base_digest="sha256:a"),  # an alias currently in the mirror
        "latest": MirrorArtifact(base_digest="sha256:a"),
        "7.2.0": MirrorArtifact(base_digest="sha256:a"),
    }
    got = reconcile_import(exp, source, mirror, NOW, GRACE)
    assert got.to_delete == []  # the aliases 7.2/latest are desired alias names → not deleted


def test_reconcile_variant_missing_source_tag_raises_clear_error() -> None:
    plan = _plan("standard", "", tags=["1.0.0", "2.0.0"], aliases={})
    source = {"1.0.0": _src("sha256:a", 30)}  # 2.0.0 missing → contract violation
    with pytest.raises(KeyError, match=r"2\.0\.0"):
        reconcile_variant(plan, source, {}, NOW, GRACE)
