"""Compute the reconcile plan for an expanded import against a destination's
mirror state (spec §8). Pure: source and mirror state are inputs.

Change detection is provenance-based: a transformed image's mirror digest differs
from its source, so we compare the mirror's recorded `base.digest` (the source
digest at build time) against the current source digest — not mirror vs source.
For multi-arch, the source digest is the index digest. The 7-day stability window
defers updates while a moving source digest settles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from houba.domain.expand import ExpandedImport, VariantPlan

DEFAULT_GRACE = timedelta(days=7)


@dataclass(frozen=True)
class SourceArtifact:
    digest: str  # current source digest (index digest for multi-arch)
    pushed_at: datetime


@dataclass(frozen=True)
class MirrorArtifact:
    base_digest: str  # recorded org.opencontainers.image.base.digest


def _classify(
    source: SourceArtifact,
    mirror: MirrorArtifact | None,
    now: datetime,
    grace: timedelta,
) -> Literal["import", "update", "skip"]:
    if mirror is None:
        return "import"
    if mirror.base_digest == source.digest:
        return "skip"
    if now - source.pushed_at < grace:
        return "skip"  # source moved too recently — let it settle
    return "update"


@dataclass(frozen=True)
class VariantReconcile:
    variant: str
    to_import: list[str]
    to_update: list[str]
    aliases: dict[str, str]


def reconcile_variant(
    plan: VariantPlan,
    source: dict[str, SourceArtifact],
    mirror: dict[str, MirrorArtifact],
    now: datetime,
    grace: timedelta = DEFAULT_GRACE,
) -> VariantReconcile:
    """Reconcile one variant against a destination's mirror state.

    Pre-condition: every tag in ``plan.tags`` must be a key in ``source`` (the
    caller — expand_import selection + the source-state fetch — must be
    consistent). A missing tag is a caller-contract violation, raised as KeyError.
    """
    to_import: list[str] = []
    to_update: list[str] = []
    for src_tag in plan.tags:
        out_tag = src_tag + plan.suffix
        try:
            src = source[src_tag]
        except KeyError as exc:
            raise KeyError(
                f"source tag {src_tag!r} absent from source state — "
                "expand_import selection and source fetch must be consistent"
            ) from exc
        decision = _classify(src, mirror.get(out_tag), now, grace)
        if decision == "import":
            to_import.append(out_tag)
        elif decision == "update":
            to_update.append(out_tag)
    aliases = {alias + plan.suffix: target + plan.suffix for alias, target in plan.aliases.items()}
    return VariantReconcile(
        variant=plan.name,
        to_import=to_import,
        to_update=to_update,
        aliases=aliases,
    )


@dataclass(frozen=True)
class ImportReconcile:
    name: str
    variants: list[VariantReconcile]
    to_delete: list[str]


def reconcile_import(
    expanded: ExpandedImport,
    source: dict[str, SourceArtifact],
    mirror: dict[str, MirrorArtifact],
    now: datetime,
    grace: timedelta = DEFAULT_GRACE,
) -> ImportReconcile:
    """Reconcile all variants of an expanded import; delegates to reconcile_variant.

    The same source pre-condition applies: every tag selected by expand_import
    must be present in ``source`` (selection and source-state fetch must be consistent).
    """
    variants = [reconcile_variant(v, source, mirror, now, grace) for v in expanded.variants]

    # Desired output names across ALL variants: concrete output tags + alias names.
    desired: set[str] = set()
    for v in expanded.variants:
        desired.update(tag + v.suffix for tag in v.tags)
        desired.update(alias + v.suffix for alias in v.aliases)

    to_delete = sorted(t for t in mirror if t not in desired)
    return ImportReconcile(name=expanded.name, variants=variants, to_delete=to_delete)
