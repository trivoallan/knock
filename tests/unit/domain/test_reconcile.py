from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from knock.domain.expand import ExpandedImport, VariantPlan
from knock.domain.reconcile import (
    ImportReconcile,
    MirrorArtifact,
    SourceArtifact,
    VariantReconcile,
    _classify,
    reconcile_import,
    reconcile_variant,
)
from knock.domain.retention import ResolvedRetention

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
    assert _classify(src, mir, NOW, GRACE) == "keep"


def test_classify_update_when_changed_and_stable() -> None:
    src = _src("sha256:b", 10)  # source moved 10 days ago → past grace
    mir = MirrorArtifact(base_digest="sha256:a")
    assert _classify(src, mir, NOW, GRACE) == "update"


def test_classify_skip_when_changed_but_within_grace() -> None:
    src = _src("sha256:b", 3)  # source moved 3 days ago → within 7-day grace
    mir = MirrorArtifact(base_digest="sha256:a")
    assert _classify(src, mir, NOW, GRACE) == "keep"


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


def test_classify_keep_is_independent_of_coverage() -> None:
    # _classify decides only rebuild-vs-keep; signature/SBOM coverage is orthogonal.
    src = _src("sha256:a", 30)
    mir = MirrorArtifact(base_digest="sha256:a", attested=False, sbom_covered=False)
    assert _classify(src, mir, NOW, GRACE) == "keep"


def test_reconcile_variant_kept_uncovered_goes_to_sbom() -> None:
    plan = _plan("standard", "", tags=["1.0.0"], aliases={})
    source = {"1.0.0": _src("sha256:a", 30)}  # unchanged → keep
    mirror = {"1.0.0": MirrorArtifact(base_digest="sha256:a", sbom_covered=False)}
    got = reconcile_variant(plan, source, mirror, NOW, GRACE)
    assert got.to_sbom == ["1.0.0"]
    assert got.to_sign == []
    assert got.to_import == [] and got.to_update == []


def test_reconcile_variant_kept_unsigned_and_uncovered_in_both() -> None:
    plan = _plan("standard", "", tags=["1.0.0"], aliases={})
    source = {"1.0.0": _src("sha256:a", 30)}
    mirror = {"1.0.0": MirrorArtifact(base_digest="sha256:a", attested=False, sbom_covered=False)}
    got = reconcile_variant(plan, source, mirror, NOW, GRACE)
    assert got.to_sign == ["1.0.0"]
    assert got.to_sbom == ["1.0.0"]


def test_reconcile_variant_kept_covered_in_neither() -> None:
    plan = _plan("standard", "", tags=["1.0.0"], aliases={})
    source = {"1.0.0": _src("sha256:a", 30)}
    # attested and sbom_covered both default to True
    mirror = {"1.0.0": MirrorArtifact(base_digest="sha256:a")}
    got = reconcile_variant(plan, source, mirror, NOW, GRACE)
    assert got.to_sign == [] and got.to_sbom == []


def test_reconcile_variant_update_never_backfills_sbom() -> None:
    # A rebuild (base changed, stable) re-attaches the SBOM itself → not a backfill candidate.
    plan = _plan("standard", "", tags=["1.0.0"], aliases={})
    source = {"1.0.0": _src("sha256:b", 10)}  # changed + stable → update
    mirror = {"1.0.0": MirrorArtifact(base_digest="sha256:a", sbom_covered=False)}
    got = reconcile_variant(plan, source, mirror, NOW, GRACE)
    assert got.to_update == ["1.0.0"]
    assert got.to_sbom == []


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


# ---------------------------------------------------------------------------
# Transform-aware change detection (Task 5)
# ---------------------------------------------------------------------------


def test_classify_transform_unchanged_falls_back_to_source_logic() -> None:
    src = SourceArtifact(digest="sha256:s", pushed_at=NOW)
    mir = MirrorArtifact(base_digest="sha256:s", transform_version="sha256:tv")
    assert _classify(src, mir, NOW, GRACE, desired_transform_version="sha256:tv") == "keep"


def test_classify_transform_changed_rebuilds_now_ignoring_grace() -> None:
    # Source unchanged + pushed just now (inside grace), but transform changed → update now.
    src = SourceArtifact(digest="sha256:s", pushed_at=NOW)
    mir = MirrorArtifact(base_digest="sha256:s", transform_version="sha256:OLD")
    assert _classify(src, mir, NOW, GRACE, desired_transform_version="sha256:NEW") == "update"


def test_classify_copy_path_unchanged_when_no_transform_either_side() -> None:
    src = SourceArtifact(digest="sha256:s", pushed_at=NOW)
    mir = MirrorArtifact(base_digest="sha256:s")  # transform_version defaults None
    assert _classify(src, mir, NOW, GRACE, desired_transform_version=None) == "keep"


# ---------------------------------------------------------------------------
# marked / to_unmark (Task 3)
# ---------------------------------------------------------------------------

_NOW_T3 = datetime(2026, 6, 12, tzinfo=UTC)


def _expanded_single_tag() -> ExpandedImport:
    # one variant, no suffix, selecting tag "7.2.0"
    return ExpandedImport(
        name="stable",
        destinations=None,
        platforms=None,
        archive=None,
        variants=[VariantPlan(name="default", suffix="", transform=[], tags=["7.2.0"], aliases={})],
    )


def test_to_unmark_is_marked_intersect_desired() -> None:
    expanded = _expanded_single_tag()
    src = {"7.2.0": SourceArtifact(digest="sha256:s", pushed_at=_NOW_T3)}
    # mirror has the desired tag (stamped) plus an obsolete tag "6.0.0"
    mirror = {
        "7.2.0": MirrorArtifact(base_digest="sha256:s"),
        "6.0.0": MirrorArtifact(base_digest="sha256:old"),
    }
    # "7.2.0" carries a stale mark and is desired again → to_unmark; "6.0.0" is undesired
    result = reconcile_import(expanded, src, mirror, _NOW_T3, marked_selection={"7.2.0"})
    assert result.to_unmark == ["7.2.0"]
    assert result.to_delete == ["6.0.0"]


def test_marked_defaults_to_empty_and_to_unmark_empty() -> None:
    expanded = _expanded_single_tag()
    src = {"7.2.0": SourceArtifact(digest="sha256:s", pushed_at=_NOW_T3)}
    mirror = {"7.2.0": MirrorArtifact(base_digest="sha256:s")}
    result = reconcile_import(expanded, src, mirror, _NOW_T3)
    assert result.to_unmark == []
    assert result.to_delete == []


# ---------------------------------------------------------------------------
# Retention marks (Task 3)
# ---------------------------------------------------------------------------


def _src_same() -> SourceArtifact:
    # source digest matches the mirror's recorded base.digest below -> _classify == skip
    return SourceArtifact(digest="sha256:s", pushed_at=NOW)


def test_reconcile_import_retention_marks_old_excess() -> None:
    plan = _plan("", "", tags=["1.0", "1.1", "1.2", "1.3"], aliases={})
    source = {t: _src_same() for t in ["1.0", "1.1", "1.2", "1.3"]}
    mirror = {
        "1.0": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=60)),
        "1.1": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=50)),
        "1.2": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=2)),
        "1.3": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=1)),
    }
    got = reconcile_import(
        _expanded([plan]),
        source,
        mirror,
        NOW,
        retention=ResolvedRetention(keep=2, older_than_days=30),
    )
    assert got.to_mark_retention == ["1.0", "1.1"]
    assert got.to_unmark_retention == []
    assert got.to_delete == []


def test_reconcile_import_retention_none_marks_nothing() -> None:
    plan = _plan("", "", tags=["1.0", "1.1"], aliases={})
    source = {t: _src_same() for t in ["1.0", "1.1"]}
    mirror = {
        "1.0": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=99)),
        "1.1": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=99)),
    }
    got = reconcile_import(_expanded([plan]), source, mirror, NOW, retention=None)
    assert got.to_mark_retention == []


def test_reconcile_import_retention_protects_alias_target() -> None:
    plan = _plan("", "", tags=["1.0", "1.1", "1.2"], aliases={"stable": "1.0"})
    source = {t: _src_same() for t in ["1.0", "1.1", "1.2"]}
    mirror = {
        "1.0": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=60)),
        "1.1": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=50)),
        "1.2": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=1)),
        "stable": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=1)),
    }
    got = reconcile_import(
        _expanded([plan]),
        source,
        mirror,
        NOW,
        retention=ResolvedRetention(keep=1, older_than_days=30),
    )
    # 1.0 is the alias target -> protected; 1.2 is the newest and kept
    assert got.to_mark_retention == ["1.1"]


def test_reconcile_import_retention_unmarks_when_no_longer_excess() -> None:
    plan = _plan("", "", tags=["1.0", "1.1"], aliases={})
    source = {t: _src_same() for t in ["1.0", "1.1"]}
    mirror = {
        "1.0": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=1)),
        "1.1": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=2)),
    }
    got = reconcile_import(
        _expanded([plan]),
        source,
        mirror,
        NOW,
        marked_retention={"1.1"},
        retention=ResolvedRetention(keep=1, older_than_days=30),
    )
    assert got.to_mark_retention == []
    assert got.to_unmark_retention == ["1.1"]


def test_reconcile_import_retention_idempotent_keeps_existing_mark() -> None:
    plan = _plan("", "", tags=["1.0", "1.1", "1.2"], aliases={})
    source = {t: _src_same() for t in ["1.0", "1.1", "1.2"]}
    mirror = {
        "1.0": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=60)),
        "1.1": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=2)),
        "1.2": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=1)),
    }
    got = reconcile_import(
        _expanded([plan]),
        source,
        mirror,
        NOW,
        marked_retention={"1.0"},
        retention=ResolvedRetention(keep=2, older_than_days=30),
    )
    assert got.to_mark_retention == []
    assert got.to_unmark_retention == []


def test_reconcile_import_retention_skips_tags_without_imported_at() -> None:
    plan = _plan("", "", tags=["1.0", "1.1", "1.2"], aliases={})
    source = {t: _src_same() for t in ["1.0", "1.1", "1.2"]}
    mirror = {
        "1.0": MirrorArtifact(base_digest="sha256:s", imported_at=None),  # undateable -> skipped
        "1.1": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=60)),
        "1.2": MirrorArtifact(base_digest="sha256:s", imported_at=NOW - timedelta(days=1)),
    }
    got = reconcile_import(
        _expanded([plan]),
        source,
        mirror,
        NOW,
        retention=ResolvedRetention(keep=1, older_than_days=30),
    )
    # dateable = {1.1, 1.2}; keep=1 protects 1.2 (newest); 1.1 old -> excess; 1.0 never considered
    assert got.to_mark_retention == ["1.1"]


# ---------------------------------------------------------------------------
# Backfill-sign plan (Task 1 — attested field)
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime(2026, 6, 15, tzinfo=UTC)


def test_skipped_unattested_tag_routes_to_sign() -> None:
    # source unchanged + already mirrored => normally "skip"; unattested => "sign".
    plan = VariantPlan(name="default", tags=["7.2.5"], suffix="", transform=[], aliases={})
    source = {"7.2.5": SourceArtifact(digest="sha256:s", pushed_at=_now() - timedelta(days=30))}
    mirror = {"7.2.5": MirrorArtifact(base_digest="sha256:s", attested=False)}
    result = reconcile_variant(plan, source, mirror, _now())
    assert result.to_sign == ["7.2.5"]
    assert result.to_import == []
    assert result.to_update == []


def test_skipped_attested_tag_does_not_sign() -> None:
    plan = VariantPlan(name="default", tags=["7.2.5"], suffix="", transform=[], aliases={})
    source = {"7.2.5": SourceArtifact(digest="sha256:s", pushed_at=_now() - timedelta(days=30))}
    mirror = {"7.2.5": MirrorArtifact(base_digest="sha256:s", attested=True)}
    result = reconcile_variant(plan, source, mirror, _now())
    assert result.to_sign == []


def test_within_grace_unattested_still_backfills_signature() -> None:
    # source moved within grace => no update, but the current mirror digest must get signed.
    plan = VariantPlan(name="default", tags=["7.2.5"], suffix="", transform=[], aliases={})
    source = {"7.2.5": SourceArtifact(digest="sha256:new", pushed_at=_now())}
    mirror = {"7.2.5": MirrorArtifact(base_digest="sha256:old", attested=False)}
    result = reconcile_variant(plan, source, mirror, _now())
    assert result.to_update == []  # within grace
    assert result.to_sign == ["7.2.5"]
