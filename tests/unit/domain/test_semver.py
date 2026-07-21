import pytest

from knock.domain.semver import SemverParts, parse_semver, sort_semver


def test_basic_ascending_order() -> None:
    assert sort_semver(["1.0.0", "0.9.0", "1.1.0"]) == ["0.9.0", "1.0.0", "1.1.0"]


def test_descending_order() -> None:
    assert sort_semver(["1.0.0", "0.9.0", "1.1.0"], reverse=True) == ["1.1.0", "1.0.0", "0.9.0"]


def test_v_prefix_treated_as_equal() -> None:
    out = sort_semver(["v1.2.3", "1.2.4", "v1.2.2"])
    assert out == ["v1.2.2", "v1.2.3", "1.2.4"]


def test_pre_release_sorts_before_final() -> None:
    out = sort_semver(["1.2.3", "1.2.3-rc1", "1.2.3-alpha"])
    assert out == ["1.2.3-alpha", "1.2.3-rc1", "1.2.3"]


def test_partial_versions_normalized() -> None:
    assert sort_semver(["1", "1.2", "1.2.3"]) == ["1", "1.2", "1.2.3"]


def test_non_semver_values_pushed_to_end() -> None:
    out = sort_semver(["1.0.0", "latest", "2.0.0", "edge"])
    assert out[:2] == ["1.0.0", "2.0.0"]
    assert set(out[2:]) == {"latest", "edge"}


@pytest.mark.parametrize("value", [[], ["v1"]])
def test_edge_cases_short_lists(value: list[str]) -> None:
    assert sort_semver(value) == value


def test_parse_semver_full() -> None:
    p = parse_semver("1.36.2")
    assert p == SemverParts(major=1, minor=36, patch=2)


def test_parse_semver_with_v_prefix_and_partials() -> None:
    assert parse_semver("v2") == SemverParts(major=2, minor=0, patch=0)
    assert parse_semver("3.4") == SemverParts(major=3, minor=4, patch=0)


def test_parse_semver_prerelease_still_parses_components() -> None:
    assert parse_semver("1.2.3-rc1") == SemverParts(major=1, minor=2, patch=3)


def test_parse_semver_non_semver_returns_none() -> None:
    assert parse_semver("latest") is None
    assert parse_semver("debian-12") is None
