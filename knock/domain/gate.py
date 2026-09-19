"""The gate between reconcile's diff and its application (D-30, form b).

knock does not call an evaluator. `reconcile --plan-out` writes a `ReconcilePlan` — every
import, update and rebuild the run would perform — and `reconcile --apply-plan` applies only
the operations a filtered copy of that plan still names. The orchestrator evaluates the source
digests in between and removes the refused entries: absence is refusal.

An approval is bound to the source DIGEST, never the tag: if upstream re-pushed the tag after
the plan was written, the live operation no longer matches and is withheld (fails closed).
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
