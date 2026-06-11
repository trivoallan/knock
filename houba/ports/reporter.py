"""Reporter port: in-flight reconcile events + the value types crossing the boundary.

The frozen dataclasses here are the port's data model (house convention). The
Pydantic RunReport tree in `houba.use_cases.report` embeds `Counts` and `ErrorInfo`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from houba.use_cases.report import RunReport

OperationKind = Literal["imported", "updated", "deleted", "aliased", "skipped"]


@dataclass(frozen=True)
class Counts:
    imported: int = 0
    updated: int = 0
    deleted: int = 0
    aliased: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class ErrorInfo:
    type: str  # exception class name, e.g. "RegctlError"
    message: str
    exit_code: int  # from houba.errors.exit_code_for


@dataclass(frozen=True)
class OperationEvent:
    policy: str
    dest_repo: str
    variant: str
    kind: OperationKind
    out_tag: str
    src_tag: str | None
    digest: str | None
    applied: bool


class Reporter(Protocol):
    """In-flight reconcile events. The use case calls these as work happens; the
    structlog adapter renders them to the stderr journal. `run_completed` takes the
    full RunReport (imported lazily to avoid a hard ports→use_cases dependency)."""

    def run_started(self, policy_count: int, *, mode: str) -> None: ...
    def policy_started(self, name: str, source: str) -> None: ...
    def operation_applied(self, ev: OperationEvent) -> None: ...
    def policy_failed(self, name: str, error: ErrorInfo) -> None: ...
    def policy_completed(self, name: str, totals: Counts) -> None: ...
    def run_completed(self, report: RunReport) -> None: ...
