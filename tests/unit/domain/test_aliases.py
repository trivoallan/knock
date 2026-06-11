from __future__ import annotations

from houba.domain.aliases import render_template, resolve_aliases


def test_render_semver_components() -> None:
    assert render_template("{major}", "1.36.2", None) == "1"
    assert render_template("{major}.{minor}", "1.36.2", None) == "1.36"
    assert render_template("{major}.{minor}.{patch}", "1.36.2", None) == "1.36.2"


def test_render_semver_on_non_semver_returns_none() -> None:
    assert render_template("{major}.{minor}", "debian-12", None) is None


def test_render_named_capture() -> None:
    rx = r"^(?P<flavor>debian|alpine)-(?P<ver>\d+)$"
    assert render_template("{flavor}", "debian-12", rx) == "debian"
    assert render_template("{flavor}-{ver}", "alpine-3", rx) == "alpine-3"


def test_render_capture_no_match_returns_none() -> None:
    rx = r"^(?P<flavor>debian)-\d+$"
    assert render_template("{flavor}", "alpine-3", rx) is None


def test_render_literal_passthrough() -> None:
    assert render_template("stable-{major}", "7.2.0", None) == "stable-7"


def test_semver_ladder() -> None:
    tags = ["1.36.1", "1.36.2", "1.37.0"]
    got = resolve_aliases(["{major}", "{major}.{minor}", "latest"], tags, None)
    assert got == {
        "1": "1.37.0",
        "1.36": "1.36.2",
        "1.37": "1.37.0",
        "latest": "1.37.0",
    }


def test_latest_picks_highest_overall() -> None:
    got = resolve_aliases(["latest"], ["2.0.0", "1.9.9", "2.1.0"], None)
    assert got == {"latest": "2.1.0"}


def test_regex_capture_grouping_lexical_fallback() -> None:
    rx = r"^(?P<flavor>debian|alpine)-(?P<ver>\d+)$"
    tags = ["debian-11", "debian-12", "alpine-3", "alpine-10"]
    got = resolve_aliases(["{flavor}"], tags, rx)
    # non-semver groups → lexical max within each flavor
    assert got == {"debian": "debian-12", "alpine": "alpine-3"}


def test_tags_not_matching_a_template_are_skipped() -> None:
    # "latest" is non-semver → skipped for the {major} template
    got = resolve_aliases(["{major}"], ["1.0.0", "2.0.0", "latest"], None)
    assert got == {"1": "1.0.0", "2": "2.0.0"}


def test_no_templates_yields_empty() -> None:
    assert resolve_aliases([], ["1.0.0"], None) == {}
