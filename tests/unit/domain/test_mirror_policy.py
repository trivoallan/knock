from __future__ import annotations

import pytest
from pydantic import ValidationError

from houba.domain.mirror_policy import (
    Archive,
    ArtifactType,
    Defaults,
    Destination,
    ImportProfile,
    Source,
    TagSelection,
    TransformStep,
    Variant,
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


def test_archive_defaults() -> None:
    a = Archive.model_validate({})
    assert a.keep == 2
    assert a.older_than_days == 30


def test_archive_camel_input() -> None:
    a = Archive.model_validate({"keep": 5, "olderThanDays": 90})
    assert a.keep == 5
    assert a.older_than_days == 90


def test_variant_minimal() -> None:
    v = Variant.model_validate({"name": "standard", "suffix": ""})
    assert v.name == "standard"
    assert v.suffix == ""
    assert v.transform is None


def test_variant_with_transform() -> None:
    v = Variant.model_validate(
        {"name": "fips", "suffix": "-fips", "transform": [{"enableFips": {}}]}
    )
    assert v.suffix == "-fips"
    assert v.transform is not None
    assert v.transform[0].name == "enableFips"


def test_defaults_all_optional() -> None:
    d = Defaults.model_validate({})
    assert d.destinations is None
    assert d.transform is None
    assert d.archive is None
    assert d.tags is None
    assert d.platforms is None


def test_defaults_populated() -> None:
    d = Defaults.model_validate(
        {
            "platforms": ["linux/amd64", "linux/arm64"],
            "destinations": [{"registry": "harbor-eu", "project": "lib", "repository": "redis"}],
            "transform": [{"injectCA": {"certs": ["corp-root-ca"]}}],
            "archive": {"keep": 2, "olderThanDays": 30},
            "tags": {"semverOnly": True, "excludeRegex": ["-rc"]},
        }
    )
    assert d.platforms == ["linux/amd64", "linux/arm64"]
    assert d.destinations[0].registry == "harbor-eu"
    assert d.transform[0].name == "injectCA"
    assert d.tags.exclude_regex == ["-rc"]


def test_import_profile_minimal() -> None:
    i = ImportProfile.model_validate({"name": "v7", "tags": {"includeRegex": "^7\\."}})
    assert i.name == "v7"
    assert i.tags.include_regex == "^7\\."
    assert i.destinations is None  # inherited from defaults at merge time
    assert i.variants is None


def test_import_profile_full() -> None:
    i = ImportProfile.model_validate(
        {
            "name": "v7",
            "tags": {"includeRegex": "^7\\.", "aliases": ["{major}.{minor}"]},
            "destinations": [{"registry": "harbor-eu", "project": "lib", "repository": "redis"}],
            "transform": [{"setTimezone": {"zone": "Europe/Paris"}}],
            "archive": {"keep": 3},
            "platforms": ["linux/amd64"],
            "variants": [{"name": "standard", "suffix": ""}],
        }
    )
    assert i.platforms == ["linux/amd64"]
    assert i.variants[0].name == "standard"
    assert i.transform[0].name == "setTimezone"
