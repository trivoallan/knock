"""The gate between reconcile's diff and its application (D-30, form b).

knock does not call an evaluator. `reconcile --plan-out` writes a `ReconcilePlan` — every
import, update and rebuild the run would perform — and `reconcile --apply-plan` applies only
the operations a filtered copy of that plan still names. The orchestrator evaluates the source
digests in between and removes the refused entries: absence is refusal.

An approval is bound to the source DIGEST, never the tag: if upstream re-pushed the tag after
the plan was written, the live operation no longer matches and is withheld (fails closed).

The same seam is played a second time for rebuilt images. With a staging registry,
`reconcile --apply-plan` pushes what it BUILDS there instead of to the destination and writes
a `StagedRebuilds` document; the orchestrator evaluates the staged digests and removes the
refused entries; `promote` places the rest. A copied image is not staged: it is byte-identical
to the source the first seam judged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ConfigDict, Field

from knock.domain.mirror_policy import _CamelModel

PlanKind = Literal["import", "update", "rebuild"]
GateKey = tuple[str, str, str, str, str]


class PlannedOperation(_CamelModel):
    model_config = ConfigDict(frozen=True)

    policy: str
    kind: PlanKind
    destination: str  # destination repository, e.g. harbor.corp/hub/redis
    tag: str  # destination tag (variant suffix included)
    source: str  # source repository, e.g. docker.io/library/redis
    source_tag: str
    source_digest: str  # what the evaluator judges: {source}@{sourceDigest}

    def key(self) -> GateKey:
        return (self.policy, self.destination, self.tag, self.kind, self.source_digest)


class ReconcilePlan(_CamelModel):
    api_version: Literal["knock.io/v1alpha1"] = "knock.io/v1alpha1"
    kind: Literal["ReconcilePlan"] = "ReconcilePlan"
    operations: list[PlannedOperation] = Field(default_factory=list)


def reconcile_plan_json_schema() -> dict[str, Any]:
    return ReconcilePlan.model_json_schema(by_alias=True)


@dataclass
class Gate:
    """`approved is None` records every planned operation and admits it (`--plan-out`, a dry
    run). Otherwise it admits exactly the approved keys and records nothing (`--apply-plan`)."""

    approved: frozenset[GateKey] | None = None
    planned: list[PlannedOperation] = field(default_factory=list)

    @classmethod
    def from_plan(cls, plan: ReconcilePlan) -> Gate:
        return cls(approved=frozenset(op.key() for op in plan.operations))

    def admits(self, op: PlannedOperation) -> bool:
        if self.approved is None:
            self.planned.append(op)
            return True
        return op.key() in self.approved


class StagedEntry(_CamelModel):
    """One rebuilt image held in the staging registry, and where it is meant to go."""

    model_config = ConfigDict(frozen=True)

    policy: str
    import_name: str = Field(alias="import")
    variant: str
    kind: PlanKind
    destination: str  # destination repository, e.g. harbor.corp/hub/redis
    tag: str  # destination tag (variant suffix included)
    source: str
    source_tag: str
    source_digest: str
    staged: str  # staged repository: the destination, re-rooted under the staging registry
    staged_digest: str  # what the evaluator judges: {staged}@{stagedDigest}
    # Aliases reconcile resolved onto this tag. Recorded here so promote replays reconcile's
    # rule instead of computing a second one from whatever the destination holds.
    aliases: tuple[str, ...] = ()


class StagedRebuilds(_CamelModel):
    api_version: Literal["knock.io/v1alpha1"] = "knock.io/v1alpha1"
    kind: Literal["StagedRebuilds"] = "StagedRebuilds"
    entries: list[StagedEntry] = Field(default_factory=list)


def staged_rebuilds_json_schema() -> dict[str, Any]:
    return StagedRebuilds.model_json_schema(by_alias=True)


def staged_repository(destination: str, *, destination_host: str, staging_host: str) -> str:
    """`destination`, re-rooted under the staging registry: same path, other host.

    Keeping the path means two destinations of one policy never collide in staging, and
    that promote can re-derive the staged location instead of trusting a file for it.
    """
    prefix = destination_host + "/"
    if not destination.startswith(prefix):
        raise ValueError(f"{destination!r} is not under {destination_host!r}")
    return f"{staging_host}/{destination[len(prefix) :]}"


def stages(*, transformed: bool) -> bool:
    """Whether an operation is held in staging: only one that builds an image."""
    return transformed
