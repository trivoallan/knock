from __future__ import annotations

from houba.domain.aliases import render_template


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
