from __future__ import annotations

from pathlib import Path

from houba.domain.mirror_policy import parse_mirror_policy


def test_timezone_example_declares_two_regional_variants() -> None:
    policy = parse_mirror_policy(Path("docs/examples/timezone/debian.yml").read_text())

    assert policy.metadata.name == "debian-tz"
    [imp] = policy.spec.imports
    assert imp.name == "slim"
    # bookworm-slim is not semver, so the policy must opt out of the semver-only filter
    assert imp.tags.semver_only is False
    assert imp.tags.include_regex == "^bookworm-slim$"

    assert imp.variants is not None
    assert [(v.name, v.suffix) for v in imp.variants] == [
        ("eu", "-eu"),
        ("us", "-us"),
    ]
    eu, us = imp.variants
    assert [(s.name, s.params) for s in eu.transform] == [
        ("setTimezone", {"zone": "Europe/Paris"}),
    ]
    assert [(s.name, s.params) for s in us.transform] == [
        ("setTimezone", {"zone": "America/New_York"}),
    ]

    [dest] = imp.destinations
    assert (dest.registry, dest.project, dest.repository) == (None, "demo", "debian")
