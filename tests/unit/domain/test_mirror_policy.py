from __future__ import annotations

import pytest
from pydantic import ValidationError

from houba.domain.mirror_policy import (
    ArtifactType,
    Destination,
    Source,
    TagSelection,
    TransformStep,
)


def test_source_parses() -> None:
    s = Source.model_validate({"registry": "docker.io", "repository": "library/redis"})
    assert s.registry == "docker.io"
    assert s.repository == "library/redis"


def test_destination_registry_optional() -> None:
    d = Destination.model_validate({"project": "lib", "repository": "redis"})
    assert d.registry is None
    assert d.project == "lib"


def test_destination_with_named_registry() -> None:
    d = Destination.model_validate(
        {"registry": "harbor-eu", "project": "lib", "repository": "redis"}
    )
    assert d.registry == "harbor-eu"


def test_artifact_type_values() -> None:
    assert ArtifactType("image") is ArtifactType.image
    assert ArtifactType("helmChart") is ArtifactType.helm_chart
    assert ArtifactType("generic") is ArtifactType.generic


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Source.model_validate({"registry": "docker.io", "repository": "r", "typo": 1})


def test_tag_selection_defaults() -> None:
    t = TagSelection.model_validate({})
    assert t.include_regex is None
    assert t.exclude_regex == []
    assert t.semver_only is True
    assert t.names == []
    assert t.aliases == []


def test_tag_selection_camel_case_input() -> None:
    t = TagSelection.model_validate(
        {
            "includeRegex": "^7\\.",
            "excludeRegex": ["-rc"],
            "semverOnly": False,
            "names": ["7.2.1-special"],
            "aliases": ["{major}.{minor}", "latest"],
        }
    )
    assert t.include_regex == "^7\\."
    assert t.exclude_regex == ["-rc"]
    assert t.semver_only is False
    assert t.names == ["7.2.1-special"]
    assert t.aliases == ["{major}.{minor}", "latest"]


def test_transform_step_from_single_key_map() -> None:
    step = TransformStep.model_validate({"injectCA": {"certs": ["corp-root-ca"]}})
    assert step.name == "injectCA"
    assert step.params == {"certs": ["corp-root-ca"]}


def test_transform_step_with_empty_params() -> None:
    step = TransformStep.model_validate({"enableFips": {}})
    assert step.name == "enableFips"
    assert step.params == {}


def test_transform_step_null_params_becomes_empty() -> None:
    step = TransformStep.model_validate({"enableFips": None})
    assert step.params == {}


def test_transform_step_rejects_multi_key() -> None:
    with pytest.raises(ValueError):
        TransformStep.model_validate({"injectCA": {}, "setTimezone": {}})


def test_transform_step_rejects_empty() -> None:
    with pytest.raises(ValueError):
        TransformStep.model_validate({})
