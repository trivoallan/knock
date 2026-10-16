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
refused entries; `promote` places the rest. Only a REMEDIATED image is staged: a copy is
byte-identical to the source the first seam judged, and a transform-only rebuild is a placement
invariant nobody judges again.

A plan operation may carry a remediation order (`remediate: {epoch}`), added by the
orchestrator: knock then applies the import's `remediate:` steps to that operation only. The
order is outside the key, like `transformed`: knock learns WHAT to repair, never who decided.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import AliasChoices, ConfigDict, Field

from knock.domain.mirror_policy import _CamelModel
from knock.domain.transforms.steps import EPOCH_PATTERN

PlanKind = Literal["import", "update", "rebuild"]
GateKey = tuple[str, str, str, str, str]


class RemediationOrder(_CamelModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Interpolated into a RUN instruction: refused at load when outside this alphabet.
    epoch: str = Field(pattern=EPOCH_PATTERN)


class PlannedOperation(_CamelModel):
    model_config = ConfigDict(frozen=True)

    policy: str
    kind: PlanKind
    destination: str  # destination repository, e.g. harbor.corp/hub/redis
    tag: str  # destination tag (variant suffix included)
    source: str  # source repository, e.g. docker.io/library/redis
    source_tag: str
    source_digest: str  # what the evaluator judges: {source}@{sourceDigest}
    # Whether applying this operation BUILDS an image (the policy resolves a transform onto it)
    # or copies the source. Informative: not part of the key, so an approval stays bound to the
    # digest and a plan filtered by a tool that drops the field still applies.
    transformed: bool = False
    # Written by the orchestrator, never by `--plan-out`: apply this import's `remediate:`
    # steps to this operation, with this epoch. Outside the key, like `transformed`.
    remediate: RemediationOrder | None = None
    # Informative: the destination tag this operation replaces carries a remediation, so an
    # orchestrator can renew the order instead of letting a rebuild undo the repair.
    remediated: bool = False

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
    orders: dict[GateKey, RemediationOrder] = field(default_factory=dict)

    @classmethod
    def from_plan(cls, plan: ReconcilePlan) -> Gate:
        return cls(
            approved=frozenset(op.key() for op in plan.operations),
            orders={op.key(): op.remediate for op in plan.operations if op.remediate},
        )

    def order(self, op: PlannedOperation) -> RemediationOrder | None:
        """The remediation the approved plan orders for `op`, if any."""
        return self.orders.get(op.key())

    def admits(self, op: PlannedOperation) -> bool:
        if self.approved is None:
            self.planned.append(op)
            return True
        return op.key() in self.approved


class StagedEntry(_CamelModel):
    """One rebuilt image held in the staging registry, and where it is meant to go."""

    model_config = ConfigDict(frozen=True)

    policy: str
    # `import` is a Python keyword: the field is `import_name`, the document key `import`.
    import_name: str = Field(
        validation_alias=AliasChoices("import", "import_name"), serialization_alias="import"
    )
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
    # The epoch of the remediation order this image was built under.
    epoch: str | None = None


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


def stages(*, remediated: bool) -> bool:
    """Whether an operation is held in staging: only one the plan orders remediated."""
    return remediated
