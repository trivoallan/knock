"""Structured reconcile result (stdout machine contract).

Tree: run → policies → targets → variants → operations, with `Counts` aggregated
at each level. Deletions attach to TargetReport.operations (the domain returns
to_delete at the import/target level, not per variant). Published as JSON Schema.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from houba.ports.reporter import Counts, ErrorInfo, OperationKind

PolicyStatus = Literal["ok", "partial", "failed"]
# VariantReport/TargetReport; kept separate from PolicyStatus to allow future divergence
NodeStatus = Literal["ok", "partial", "failed"]
RunStatus = Literal["ok", "partial", "failed"]
RunMode = Literal["apply", "dry-run"]


class Operation(BaseModel):
    kind: OperationKind
    out_tag: str
    src_tag: str | None = None
    digest: str | None = None
    applied: bool  # False => planned only (dry-run) or failed
    error: ErrorInfo | None = None  # set => this operation failed


class VariantReport(BaseModel):
    name: str
    suffix: str
    status: NodeStatus = "ok"
    totals: Counts
    operations: list[Operation]


class TargetReport(BaseModel):
    dest_repo: str
    status: NodeStatus = "ok"
    variants: list[VariantReport]
    operations: list[Operation]  # target-level ops (deletions)
    totals: Counts


class PolicyReport(BaseModel):
    name: str
    source: str
    status: PolicyStatus
    error: ErrorInfo | None = None
    totals: Counts
    targets: list[TargetReport]


class RunReport(BaseModel):
    mode: RunMode
    status: RunStatus
    totals: Counts
    policies: list[PolicyReport]


def report_exit_code(report: RunReport) -> int:
    """0 when nothing failed; otherwise the worst (max) failure exit code,
    across both policy-level errors and per-operation errors."""
    codes: list[int] = []
    for p in report.policies:
        if p.error is not None:
            codes.append(p.error.exit_code)
        for tgt in p.targets:
            for v in tgt.variants:
                codes += [op.error.exit_code for op in v.operations if op.error is not None]
            codes += [op.error.exit_code for op in tgt.operations if op.error is not None]
    return max(codes) if codes else 0


def run_report_json_schema() -> dict[str, Any]:
    """JSON Schema for a RunReport — published for CI consumers to validate output."""
    return RunReport.model_json_schema()
