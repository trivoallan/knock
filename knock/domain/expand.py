"""Combine selection + aliases + variant expansion into an ExpandedImport.

Pure: given a ResolvedImport and the upstream tag list, produce — per variant —
the selected concrete tags and the resolved aliases (un-suffixed). The variant
suffix is carried, not applied; Phase 3 applies it when reconciling.
"""

from __future__ import annotations

from dataclasses import dataclass

from knock.domain.aliases import resolve_aliases
from knock.domain.mirror_policy import Archive, Destination, TransformStep
from knock.domain.policy_merge import ResolvedImport
from knock.domain.selection import select_tags
from knock.domain.variants import expand_variants


@dataclass(frozen=True)
class VariantPlan:
    name: str
    suffix: str
    transform: list[TransformStep]
    tags: list[str]  # selected concrete source tags (un-suffixed)
    aliases: dict[str, str]  # alias name → concrete target tag (un-suffixed)


@dataclass(frozen=True)
class ExpandedImport:
    name: str
    destinations: list[Destination] | None
    platforms: list[str] | None
    archive: Archive | None
    variants: list[VariantPlan]
    owners: list[str] | None = None
    vendor: str | None = None


def expand_import(resolved: ResolvedImport, source_tags: list[str]) -> ExpandedImport:
    tags = select_tags(resolved.tags, source_tags)
    aliases = resolve_aliases(resolved.tags.aliases, tags, resolved.tags.include_regex)
    plans = [
        VariantPlan(
            name=v.name,
            suffix=v.suffix,
            transform=v.transform,
            tags=tags,
            aliases=aliases,
        )
        for v in expand_variants(resolved)
    ]
    return ExpandedImport(
        name=resolved.name,
        destinations=resolved.destinations,
        platforms=resolved.platforms,
        archive=resolved.archive,
        variants=plans,
        owners=resolved.owners,
        vendor=resolved.vendor,
    )
