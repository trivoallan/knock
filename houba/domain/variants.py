"""Expand an import's variants into concrete (name, suffix, transform) triples.

Absent variants => a single implicit `default` variant (no suffix) using the
resolved transform. An explicit variant inherits the resolved transform unless it
declares its own (spec §4.1).
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.domain.mirror_policy import TransformStep
from houba.domain.policy_merge import ResolvedImport


@dataclass(frozen=True)
class ResolvedVariant:
    name: str
    suffix: str
    transform: list[TransformStep]


def expand_variants(resolved: ResolvedImport) -> list[ResolvedVariant]:
    if resolved.variants is None:
        return [ResolvedVariant(name="default", suffix="", transform=resolved.transform)]
    return [
        ResolvedVariant(
            name=v.name,
            suffix=v.suffix,
            transform=v.transform if v.transform is not None else resolved.transform,
        )
        for v in resolved.variants
    ]
