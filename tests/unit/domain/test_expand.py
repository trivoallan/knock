from __future__ import annotations

from houba.domain.expand import ExpandedImport, VariantPlan, expand_import
from houba.domain.mirror_policy import Spec
from houba.domain.policy_merge import resolve_imports

SOURCE = ["7.2.0", "7.2.1", "7.3.0", "latest"]


def _resolved(import_body: dict):
    body = {
        "artifactType": "image",
        "source": {"registry": "docker.io", "repository": "redis"},
        "imports": [import_body],
    }
    return resolve_imports(Spec.model_validate(body))[0]


def test_expand_single_default_variant() -> None:
    resolved = _resolved(
        {
            "name": "v7",
            "tags": {"includeRegex": "^7\\.", "aliases": ["{major}.{minor}", "latest"]},
            "destinations": [{"registry": "eu", "project": "lib", "repository": "redis"}],
            "platforms": ["linux/amd64"],
        }
    )
    expanded = expand_import(resolved, SOURCE)
    assert isinstance(expanded, ExpandedImport)
    assert expanded.name == "v7"
    assert expanded.destinations[0].registry == "eu"
    assert expanded.platforms == ["linux/amd64"]
    [variant] = expanded.variants
    assert isinstance(variant, VariantPlan)
    assert variant.name == "default"
    assert variant.suffix == ""
    assert set(variant.tags) == {"7.2.0", "7.2.1", "7.3.0"}  # 'latest' excluded by includeRegex
    assert variant.aliases == {"7.2": "7.2.1", "7.3": "7.3.0", "latest": "7.3.0"}


def test_expand_multiple_variants_share_tags_and_aliases() -> None:
    resolved = _resolved(
        {
            "name": "v7",
            "tags": {"includeRegex": "^7\\.", "aliases": ["{major}.{minor}"]},
            "transform": [{"injectCA": {}}],
            "variants": [
                {"name": "standard", "suffix": ""},
                {"name": "fips", "suffix": "-fips", "transform": [{"enableFips": {}}]},
            ],
        }
    )
    expanded = expand_import(resolved, SOURCE)
    assert [v.name for v in expanded.variants] == ["standard", "fips"]
    standard, fips = expanded.variants
    # same selected tags + aliases across variants; suffix/transform differ
    assert standard.tags == fips.tags
    assert standard.aliases == fips.aliases == {"7.2": "7.2.1", "7.3": "7.3.0"}
    assert standard.suffix == "" and fips.suffix == "-fips"
    assert [s.name for s in fips.transform] == ["enableFips"]


def test_expand_no_aliases() -> None:
    resolved = _resolved({"name": "v", "tags": {"includeRegex": "^7\\."}})
    [variant] = expand_import(resolved, SOURCE).variants
    assert variant.aliases == {}


def test_expand_carries_owners() -> None:
    resolved = resolve_imports(
        Spec.model_validate(
            {
                "artifactType": "image",
                "source": {"registry": "docker.io", "repository": "library/redis"},
                "imports": [{"name": "v", "tags": {}, "owners": ["group:default/payments"]}],
            }
        )
    )[0]
    expanded = expand_import(resolved, ["1.0.0"])
    assert expanded.owners == ["group:default/payments"]


def test_expand_carries_vendor() -> None:
    resolved = resolve_imports(
        Spec.model_validate(
            {
                "artifactType": "image",
                "source": {"registry": "docker.io", "repository": "library/redis"},
                "imports": [{"name": "v", "tags": {}, "vendor": "ACME Platform"}],
            }
        )
    )[0]
    expanded = expand_import(resolved, ["1.0.0"])
    assert expanded.vendor == "ACME Platform"
