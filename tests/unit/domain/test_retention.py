from __future__ import annotations

from houba.domain.mirror_policy import Archive
from houba.domain.retention import (
    DEFAULT_KEEP,
    DEFAULT_OLDER_THAN_DAYS,
    ResolvedRetention,
    resolve_archive,
)


def test_resolve_archive_both_none_is_off() -> None:
    assert resolve_archive(None, None) is None


def test_resolve_archive_global_only() -> None:
    assert resolve_archive(None, Archive(keep=5, older_than_days=10)) == ResolvedRetention(
        keep=5, older_than_days=10
    )


def test_resolve_archive_policy_overrides_global_per_field() -> None:
    # policy sets only keep; older_than_days falls through to global
    got = resolve_archive(Archive(keep=9), Archive(keep=5, older_than_days=10))
    assert got == ResolvedRetention(keep=9, older_than_days=10)


def test_resolve_archive_falls_through_to_constant_defaults() -> None:
    got = resolve_archive(Archive(keep=7), None)
    assert got == ResolvedRetention(keep=7, older_than_days=DEFAULT_OLDER_THAN_DAYS)


def test_resolve_archive_empty_policy_uses_global_then_constants() -> None:
    assert resolve_archive(Archive(), Archive(keep=4)) == ResolvedRetention(
        keep=4, older_than_days=DEFAULT_OLDER_THAN_DAYS
    )
    assert resolve_archive(Archive(), None) == ResolvedRetention(
        keep=DEFAULT_KEEP, older_than_days=DEFAULT_OLDER_THAN_DAYS
    )


def test_resolve_archive_keep_falls_through_to_constant_default() -> None:
    got = resolve_archive(Archive(older_than_days=7), None)
    assert got == ResolvedRetention(keep=DEFAULT_KEEP, older_than_days=7)


# ---------------------------------------------------------------------------
# select_retention_excess
# ---------------------------------------------------------------------------

from datetime import UTC, datetime, timedelta  # noqa: E402

from houba.domain.retention import select_retention_excess  # noqa: E402

_UTC = UTC
_NOW = datetime(2026, 6, 14, tzinfo=_UTC)


def _at(days_ago: int) -> datetime:
    return _NOW - timedelta(days=days_ago)


def test_excess_requires_both_beyond_keep_and_old() -> None:
    kept = {"a": _at(5), "b": _at(40), "c": _at(50), "d": _at(60)}
    # newest-first a,b,c,d; keep=2 protects a,b; c,d are >30d old -> excess
    got = select_retention_excess(kept, keep=2, older_than=timedelta(days=30), now=_NOW)
    assert got == ["c", "d"]


def test_keep_guard_protects_recent_even_if_old() -> None:
    kept = {"a": _at(100), "b": _at(90)}
    # both old, but keep=2 protects both (none beyond rank)
    got = select_retention_excess(kept, keep=2, older_than=timedelta(days=30), now=_NOW)
    assert got == []


def test_age_guard_protects_young_even_if_beyond_keep() -> None:
    kept = {"a": _at(1), "b": _at(2), "c": _at(3)}
    # keep=1 -> b,c beyond keep, but all younger than 30d
    got = select_retention_excess(kept, keep=1, older_than=timedelta(days=30), now=_NOW)
    assert got == []


def test_protected_excluded_from_ranking_and_marking() -> None:
    kept = {"a": _at(5), "b": _at(40), "c": _at(50)}
    got = select_retention_excess(
        kept, keep=1, older_than=timedelta(days=30), now=_NOW, protected=frozenset({"c"})
    )
    # c removed first; of {a,b} keep=1 protects a; b old -> excess
    assert got == ["b"]


def test_empty_kept_is_empty() -> None:
    assert select_retention_excess({}, keep=2, older_than=timedelta(days=30), now=_NOW) == []
