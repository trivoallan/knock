from __future__ import annotations

from knock.domain.mirror_policy import TagSelection
from knock.domain.selection import select_tags

SOURCE = ["1.36.0", "1.36.1", "1.37.0", "2.0.0", "2.0.0-rc1", "latest", "1.36.1-special"]


def _sel(**kw: object) -> TagSelection:
    return TagSelection.model_validate(kw)


def test_include_regex_keeps_matches() -> None:
    got = select_tags(_sel(includeRegex=r"^1\.", semverOnly=False), SOURCE)
    assert set(got) == {"1.36.0", "1.36.1", "1.37.0", "1.36.1-special"}


def test_no_include_regex_keeps_all_when_not_semver_only() -> None:
    got = select_tags(_sel(semverOnly=False), SOURCE)
    assert set(got) == set(SOURCE)


def test_exclude_regex_drops_matches() -> None:
    got = select_tags(_sel(semverOnly=False, excludeRegex=[r"-rc", r"-special"]), SOURCE)
    assert "2.0.0-rc1" not in got
    assert "1.36.1-special" not in got


def test_semver_only_drops_non_semver() -> None:
    got = select_tags(_sel(includeRegex=r".*", semverOnly=True), SOURCE)
    assert "latest" not in got  # non-semver → dropped
    assert "2.0.0-rc1" in got  # prerelease IS semver → kept
    assert "1.36.1-special" in got  # prerelease IS semver (-special) → kept
    assert "1.36.0" in got


def test_names_bypass_filters_but_must_exist_upstream() -> None:
    got = select_tags(
        _sel(includeRegex=r"^1\.", semverOnly=True, names=["latest", "9.9.9-absent"]),
        SOURCE,
    )
    assert "latest" in got  # bypasses semverOnly + includeRegex
    assert "9.9.9-absent" not in got  # not in source → not selectable


def test_names_bypass_exclude() -> None:
    got = select_tags(
        _sel(semverOnly=False, excludeRegex=[r"-special"], names=["1.36.1-special"]),
        SOURCE,
    )
    assert "1.36.1-special" in got  # explicit name wins over exclude


def test_result_has_no_duplicates() -> None:
    got = select_tags(_sel(includeRegex=r"^1\.36", semverOnly=False, names=["1.36.0"]), SOURCE)
    assert sorted(got) == sorted(set(got))
