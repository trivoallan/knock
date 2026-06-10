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
)


@dataclass(frozen=True)
class ResolvedImport:
    name: str
    tags: TagSelection
    destinations: list[Destination] | None
    transform: list[TransformStep]
    archive: Archive | None
    platforms: list[str] | None


def _merge_tags(default: TagSelection | None, override: TagSelection) -> TagSelection:
    if default is None:
        return override
    # shallow-merge: a field the override set explicitly wins; otherwise inherit.
    # `model_fields_set` tells us which fields were explicitly provided.
    merged = default.model_dump(by_alias=False)
    for field in override.model_fields_set:
        merged[field] = getattr(override, field)
    return TagSelection.model_validate(merged)


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
        archive = imp.archive if imp.archive is not None else (d.archive if d else None)
        platforms = imp.platforms if imp.platforms is not None else (d.platforms if d else None)
        resolved.append(
            ResolvedImport(
                name=imp.name,
                tags=tags,
                destinations=destinations,
                transform=transform,
                archive=archive,
                platforms=platforms,
            )
        )
    return resolved
