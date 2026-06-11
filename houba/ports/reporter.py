"""Reporter port: in-flight reconcile events + the value types crossing the boundary.

The frozen dataclasses here are the port's data model (house convention). The
Pydantic RunReport tree in `houba.use_cases.report` embeds `Counts` and `ErrorInfo`.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    kind: str  # imported|updated|deleted|aliased|skipped
    out_tag: str
    src_tag: str | None
    digest: str | None
    applied: bool
