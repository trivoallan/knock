from __future__ import annotations

from houba.ports.reporter import Counts, ErrorInfo, OperationEvent
from houba.use_cases.report import RunReport


class FakeReporter:
    """Journals every Reporter call so use-case tests can assert on emitted events."""

    def __init__(self) -> None:
        self.runs_started: list[tuple[int, str]] = []
        self.policies_started: list[tuple[str, str]] = []
        self.operations: list[OperationEvent] = []
        self.failures: list[tuple[str, ErrorInfo]] = []
        self.policies_completed: list[tuple[str, Counts]] = []
        self.runs_completed: list[RunReport] = []

    def run_started(self, policy_count: int, *, mode: str) -> None:
        self.runs_started.append((policy_count, mode))

    def policy_started(self, name: str, source: str) -> None:
        self.policies_started.append((name, source))

    def operation_applied(self, ev: OperationEvent) -> None:
        self.operations.append(ev)

    def policy_failed(self, name: str, error: ErrorInfo) -> None:
        self.failures.append((name, error))

    def policy_completed(self, name: str, totals: Counts) -> None:
        self.policies_completed.append((name, totals))

    def run_completed(self, report: RunReport) -> None:
        self.runs_completed.append(report)
