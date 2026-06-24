from datetime import timedelta

import pytest

from houba.domain.verify import Requirement, parse_duration, parse_requirements
from houba.errors import ConfigError


@pytest.mark.parametrize(
    "text,expected",
    [("7d", timedelta(days=7)), ("12h", timedelta(hours=12)),
     ("30m", timedelta(minutes=30)), ("45s", timedelta(seconds=45))],
)
def test_parse_duration_units(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("bad", ["", "7", "7x", "d", "-3d", "1.5h"])
def test_parse_duration_rejects_garbage(bad):
    with pytest.raises(ConfigError):
        parse_duration(bad)


def test_parse_requirements_default_and_subset():
    assert parse_requirements("scan-pass") == {Requirement.scan_pass}
    assert parse_requirements("scan-pass,stamp,sbom") == {
        Requirement.scan_pass, Requirement.stamp, Requirement.sbom
    }


def test_parse_requirements_rejects_unknown():
    with pytest.raises(ConfigError):
        parse_requirements("scan-pass,bogus")
