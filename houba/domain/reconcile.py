"""Compute the reconcile plan for an expanded import against a destination's
mirror state (spec §8). Pure: source and mirror state are inputs.

Change detection is provenance-based: a transformed image's mirror digest differs
from its source, so we compare the mirror's recorded `base.digest` (the source
digest at build time) against the current source digest — not mirror vs source.
For multi-arch, the source digest is the index digest. The 7-day stability window
defers updates while a moving source digest settles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from houba.domain.expand import ExpandedImport, VariantPlan
from houba.domain.retention import ResolvedRetention, select_retention_excess

DEFAULT_GRACE = timedelta(days=7)


@dataclass(frozen=True)
class SourceArtifact:
    digest: str  # current source digest (index digest for multi-arch)
    pushed_at: datetime
    revision: str | None = None  # upstream-declared org.opencontainers.image.revision, if any


@dataclass(frozen=True)
class MirrorArtifact:
    base_digest: str  # recorded org.opencontainers.image.base.digest
    transform_version: str | None = None  # recorded {prefix}.transform.version
    imported_at: datetime | None = None  # parsed org.opencontainers.image.created (stamp time)
    attested: bool = True  # does this mirror digest already carry a signed houba attestation?


def _classify(
    source: SourceArtifact,
    mirror: MirrorArtifact | None,
    now: datetime,
    grace: timedelta,
    *,
    desired_transform_version: str | None = None,
) -> Literal["import", "update", "skip", "sign"]:
    if mirror is None:
        return "import"
    transform_unchanged = mirror.transform_version == desired_transform_version
    source_unchanged = mirror.base_digest == source.digest
    if not transform_unchanged:
        return "update"  # operator changed the hardening → rebuild now, no grace
    if not source_unchanged and now - source.pushed_at >= grace:
        return "update"  # source moved and settled
    # Keeping the current mirror digest (skip) — backfill its signature if unsigned.
    return "skip" if mirror.attested else "sign"


@dataclass(frozen=True)
class VariantReconcile:
    variant: str
    to_import: list[str]
    to_update: list[str]
    aliases: dict[str, str]
    to_sign: list[str] = field(default_factory=list)


def reconcile_variant(
    plan: VariantPlan,
    source: dict[str, SourceArtifact],
    mirror: dict[str, MirrorArtifact],
    now: datetime,
    grace: timedelta = DEFAULT_GRACE,
    *,
    desired_transform_version: str | None = None,
) -> VariantReconcile:
    """Reconcile one variant against a destination's mirror state.

    Pre-condition: every tag in ``plan.tags`` must be a key in ``source`` (the
    caller — expand_import selection + the source-state fetch — must be
    consistent). A missing tag is a caller-contract violation, raised as KeyError.
    """
    to_import: list[str] = []
    to_update: list[str] = []
    to_sign: list[str] = []
    for src_tag in plan.tags:
        out_tag = src_tag + plan.suffix
        try:
            src = source[src_tag]
        except KeyError as exc:
            raise KeyError(
                f"source tag {src_tag!r} absent from source state — "
                "expand_import selection and source fetch must be consistent"
            ) from exc
        decision = _classify(
            src,
            mirror.get(out_tag),
            now,
            grace,
            desired_transform_version=desired_transform_version,
        )
        if decision == "import":
            to_import.append(out_tag)
        elif decision == "update":
            to_update.append(out_tag)
        elif decision == "sign":
            to_sign.append(out_tag)
    aliases = {alias + plan.suffix: target + plan.suffix for alias, target in plan.aliases.items()}
    return VariantReconcile(
        variant=plan.name,
        to_import=to_import,
        to_update=to_update,
        aliases=aliases,
        to_sign=to_sign,
    )


@dataclass(frozen=True)
class ImportReconcile:
    name: str
    variants: list[VariantReconcile]
    to_delete: list[str]
    to_unmark: list[str]
    to_mark_retention: list[str] = field(default_factory=list)
    to_unmark_retention: list[str] = field(default_factory=list)


def reconcile_import(
    expanded: ExpandedImport,
    source: dict[str, SourceArtifact],
    mirror: dict[str, MirrorArtifact],
    now: datetime,
    grace: timedelta = DEFAULT_GRACE,
    *,
    marked_selection: set[str] | None = None,
    marked_retention: set[str] | None = None,
    retention: ResolvedRetention | None = None,
    transform_versions: dict[str, str | None] | None = None,
) -> ImportReconcile:
    """Reconcile all variants of an expanded import; delegates to reconcile_variant.

    Two soft-delete sources, kept disjoint: ``to_delete`` (selection — mirror tags no
    longer desired) and ``to_mark_retention`` (retention — valid, in-selection tags
    beyond ``keep`` newest and older than the window). ``marked_selection`` /
    ``marked_retention`` are the mirror tags already carrying a pending-deletion
    referrer, partitioned by ``reason`` by the use case; tags that re-entered the
    desired set (``to_unmark``) or are no longer excess (``to_unmark_retention``) have
    their marks cleared. Mode-agnostic: purge vs mark is applied by the use case.
    """
    marked_selection = marked_selection or set()
    marked_retention = marked_retention or set()
    tv = transform_versions or {}
    variants = [
        reconcile_variant(v, source, mirror, now, grace, desired_transform_version=tv.get(v.name))
        for v in expanded.variants
    ]

    # Desired output names across ALL variants: concrete output tags + alias names.
    desired: set[str] = set()
    for v in expanded.variants:
        desired.update(tag + v.suffix for tag in v.tags)
        desired.update(alias + v.suffix for alias in v.aliases)

    to_delete = sorted(t for t in mirror if t not in desired)
    to_unmark = sorted(t for t in marked_selection if t in desired)

    retention_excess: set[str] = set()
    if retention is not None:
        older_than = timedelta(days=retention.older_than_days)
        for v in expanded.variants:
            alias_targets = frozenset(target + v.suffix for target in v.aliases.values())
            kept: dict[str, datetime] = {}
            for src_tag in v.tags:
                out_tag = src_tag + v.suffix
                ma = mirror.get(out_tag)
                if ma is not None and ma.imported_at is not None:
                    kept[out_tag] = ma.imported_at
            retention_excess.update(
                select_retention_excess(
                    kept,
                    keep=retention.keep,
                    older_than=older_than,
                    now=now,
                    protected=alias_targets,
                )
            )

    to_mark_retention = sorted(retention_excess - marked_retention)
    to_unmark_retention = sorted(marked_retention - retention_excess)

    return ImportReconcile(
        name=expanded.name,
        variants=variants,
        to_delete=to_delete,
        to_unmark=to_unmark,
        to_mark_retention=to_mark_retention,
        to_unmark_retention=to_unmark_retention,
    )
