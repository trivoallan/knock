from pathlib import Path

import pytest

from houba.domain.properties import Properties, parse_properties
from houba.errors import PropertiesValidationError

FIXTURES = Path(__file__).parents[2] / "fixtures" / "synthetic"


def test_parse_minimal_applies_defaults() -> None:
    p = parse_properties((FIXTURES / "properties_minimal.yml").read_text())

    assert isinstance(p, Properties)
    assert p.source.registry == "docker.io"
    assert p.source.repository == "library/busybox"
    assert p.destination.harbor == "blue"
    assert p.tags.semver_only is True  # défaut
    assert p.tags.exclude_regex == []  # défaut
    assert p.flags.set_timezone is True  # défaut
    assert p.archive.keep == 2
    assert p.archive.older_than_days == 30
    assert p.eol.product is None


def test_parse_full_overrides_defaults() -> None:
    p = parse_properties((FIXTURES / "properties_full.yml").read_text())

    assert p.destination.harbor == "both"
    assert p.tags.include_regex == r"^v\d+\.\d+\.\d+$"
    assert p.tags.exclude_regex == ["-rc"]
    assert p.flags.add_apt_repos is True
    assert p.eol.product == "kubernetes"
    assert p.archive.keep == 3


def test_missing_required_field_raises() -> None:
    yaml = """
    source:
      registry: docker.io
    destination:
      harbor: blue
      project: lib
      repository: r
    """
    with pytest.raises(PropertiesValidationError):
        parse_properties(yaml)


def test_invalid_harbor_choice_raises() -> None:
    yaml = """
    source:
      registry: docker.io
      repository: a/b
    destination:
      harbor: purple
      project: lib
      repository: r
    """
    with pytest.raises(PropertiesValidationError):
        parse_properties(yaml)


def test_invalid_yaml_raises() -> None:
    with pytest.raises(PropertiesValidationError):
        parse_properties("source: [unbalanced")
