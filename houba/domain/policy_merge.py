"""Resolve `defaults` into each `import` (spec §3.4, rule B).

Maps (`tags`, `archive`) shallow-merge key-by-key, one level; lists (`transform`,
`destinations`, `platforms`) replace wholesale. Merge is decided on *field presence
in the raw input*, so a field the import omitted is taken from defaults — Pydantic
default values do not count as "present".
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.domain.mirror_policy import (
    Archive,
    Destination,
    Spec,
    TagSelection,
    TransformStep,
    Variant,
)
from houba.errors import PolicyValidationError


@dataclass(frozen=True)
class ResolvedImport:
    name: str
    tags: TagSelection
    destinations: list[Destination] | None
    transform: list[TransformStep]
    archive: Archive | None
    platforms: list[str] | None
    variants: list[Variant] | None
    owners: list[str] | None
    vendor: str | None


def _merge_tags(default: TagSelection, override: TagSelection) -> TagSelection:
    # shallow-merge: a field the override set explicitly wins; otherwise inherit.
    # `model_fields_set` tells us which fields were explicitly provided.
    merged = default.model_dump(by_alias=False)
    for field in override.model_fields_set:
        merged[field] = getattr(override, field)
    return TagSelection.model_validate(merged)


def _merge_archive(default: Archive, override: Archive) -> Archive:
    # shallow-merge: a field the override set explicitly wins; otherwise inherit.
    merged = default.model_dump(by_alias=False)
    for field in override.model_fields_set:
        merged[field] = getattr(override, field)
    return Archive.model_validate(merged)


def resolve_imports(spec: Spec) -> list[ResolvedImport]:
    d = spec.defaults
    resolved: list[ResolvedImport] = []
    for imp in spec.imports:
        tags = imp.tags if d is None or d.tags is None else _merge_tags(d.tags, imp.tags)
        destinations = (
            imp.destinations if imp.destinations is not None else (d.destinations if d else None)
        )
        transform = (
            imp.transform if imp.transform is not None else ((d.transform if d else None) or [])
        )
        archive: Archive | None
        if imp.archive is not None:
            archive = (
                _merge_archive(d.archive, imp.archive)
                if d is not None and d.archive is not None
                else imp.archive
            )
        else:
            archive = d.archive if d is not None else None
        platforms = imp.platforms if imp.platforms is not None else (d.platforms if d else None)
        owners = imp.owners if imp.owners is not None else (d.owners if d else None)
        vendor = imp.vendor if imp.vendor is not None else (d.vendor if d else None)
        if transform and platforms is not None and len(platforms) > 1:
            raise PolicyValidationError(
                f"multi-platform rebuild is not supported (import '{imp.name}'): "
                f"a transform with more than one platform; specify a single platform "
                f"or remove the transform"
            )
        resolved.append(
            ResolvedImport(
                name=imp.name,
                tags=tags,
                destinations=destinations,
                transform=transform,
                archive=archive,
                platforms=platforms,
                variants=imp.variants,
                owners=owners,
                vendor=vendor,
            )
        )
    return resolved
