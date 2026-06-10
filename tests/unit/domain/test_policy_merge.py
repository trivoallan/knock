from __future__ import annotations

from houba.domain.mirror_policy import Spec
from houba.domain.policy_merge import ResolvedImport, resolve_imports


def _spec(defaults: dict | None, imports: list[dict]) -> Spec:
    body: dict = {
        "artifactType": "image",
        "source": {"registry": "docker.io", "repository": "library/redis"},
        "imports": imports,
    }
    if defaults is not None:
        body["defaults"] = defaults
    return Spec.model_validate(body)


def test_import_inherits_all_defaults() -> None:
    spec = _spec(
        defaults={
            "platforms": ["linux/amd64"],
            "destinations": [{"registry": "eu", "project": "lib", "repository": "redis"}],
            "transform": [{"setTimezone": {"zone": "Europe/Paris"}}],
            "archive": {"keep": 2, "olderThanDays": 30},
            "tags": {"semverOnly": True, "excludeRegex": ["-rc"]},
        },
        imports=[{"name": "v7", "tags": {"includeRegex": "^7\\."}}],
    )
    [resolved] = resolve_imports(spec)
    assert isinstance(resolved, ResolvedImport)
    assert resolved.platforms == ["linux/amd64"]
    assert resolved.destinations[0].registry == "eu"
    assert resolved.transform[0].name == "setTimezone"
    assert resolved.archive.keep == 2
    assert resolved.tags.include_regex == "^7\\."
    assert resolved.tags.semver_only is True
    assert resolved.tags.exclude_regex == ["-rc"]


def test_tags_shallow_merge_import_overrides_key() -> None:
    spec = _spec(
        defaults={"tags": {"semverOnly": True, "excludeRegex": ["-rc"]}},
        imports=[{"name": "v", "tags": {"includeRegex": "^1\\.", "semverOnly": False}}],
    )
    [resolved] = resolve_imports(spec)
    assert resolved.tags.semver_only is False
    assert resolved.tags.exclude_regex == ["-rc"]
    assert resolved.tags.include_regex == "^1\\."


def test_transform_list_replaced_not_merged() -> None:
    spec = _spec(
        defaults={"transform": [{"injectCA": {}}, {"setTimezone": {}}]},
        imports=[{"name": "v", "tags": {}, "transform": [{"enableFips": {}}]}],
    )
    [resolved] = resolve_imports(spec)
    assert [s.name for s in resolved.transform] == ["enableFips"]


def test_destinations_list_replaced() -> None:
    spec = _spec(
        defaults={"destinations": [{"registry": "eu", "project": "lib", "repository": "r"}]},
        imports=[
            {
                "name": "v",
                "tags": {},
                "destinations": [{"registry": "us", "project": "legacy", "repository": "r"}],
            }
        ],
    )
    [resolved] = resolve_imports(spec)
    assert [d.registry for d in resolved.destinations] == ["us"]


def test_missing_defaults_uses_import_only() -> None:
    spec = _spec(
        defaults=None,
        imports=[
            {
                "name": "v",
                "tags": {"includeRegex": "^1\\."},
                "destinations": [{"project": "lib", "repository": "r"}],
                "platforms": ["linux/amd64"],
            }
        ],
    )
    [resolved] = resolve_imports(spec)
    assert resolved.destinations[0].project == "lib"
    assert resolved.platforms == ["linux/amd64"]
    assert resolved.archive is None
    assert resolved.transform == []


def test_empty_tags_inherits_defaults_tags_wholesale() -> None:
    spec = _spec(
        defaults={"tags": {"semverOnly": False, "excludeRegex": ["-rc"]}},
        imports=[{"name": "v", "tags": {}}],
    )
    [resolved] = resolve_imports(spec)
    # import.tags sets no fields (model_fields_set is empty) → inherit defaults wholesale.
    # semverOnly comes from the default (False), NOT the model default (True): merge is
    # presence-based, so an omitted field is inherited, not overridden by its model default.
    assert resolved.tags.semver_only is False
    assert resolved.tags.exclude_regex == ["-rc"]
