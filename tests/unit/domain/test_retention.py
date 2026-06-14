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
