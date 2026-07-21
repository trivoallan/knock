from __future__ import annotations

from knock.domain.mirror_policy import Spec
from knock.domain.policy_merge import resolve_imports
from knock.domain.variants import ResolvedVariant, expand_variants


def _resolved(import_body: dict, defaults: dict | None = None):
    body: dict = {
        "artifactType": "image",
        "source": {"registry": "docker.io", "repository": "r"},
        "imports": [import_body],
    }
    if defaults is not None:
        body["defaults"] = defaults
    return resolve_imports(Spec.model_validate(body))[0]


def test_no_variants_yields_implicit_default() -> None:
    resolved = _resolved(
        {"name": "v", "tags": {}, "transform": [{"setTimezone": {}}]},
    )
    [variant] = expand_variants(resolved)
    assert variant == ResolvedVariant(name="default", suffix="", transform=resolved.transform)


def test_no_variants_no_transform_yields_empty_transform() -> None:
    resolved = _resolved({"name": "v", "tags": {}})
    [variant] = expand_variants(resolved)
    assert variant.name == "default"
    assert variant.transform == []


def test_explicit_variants_with_and_without_transform_override() -> None:
    resolved = _resolved(
        {
            "name": "v7",
            "tags": {},
            "transform": [{"injectCA": {}}],
            "variants": [
                {"name": "standard", "suffix": ""},
                {"name": "fips", "suffix": "-fips", "transform": [{"enableFips": {}}]},
            ],
        }
    )
    standard, fips = expand_variants(resolved)
    assert standard.suffix == ""
    assert [s.name for s in standard.transform] == ["injectCA"]  # inherited
    assert fips.suffix == "-fips"
    assert [s.name for s in fips.transform] == ["enableFips"]  # overridden
