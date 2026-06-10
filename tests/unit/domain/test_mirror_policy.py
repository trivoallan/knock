from __future__ import annotations

import pytest
from pydantic import ValidationError

from houba.domain.mirror_policy import ArtifactType, Destination, Source


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
