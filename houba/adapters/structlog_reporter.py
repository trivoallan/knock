"""Reporter adapter: renders in-flight reconcile events to the structlog journal
(stderr). Output stream/format is owned by `houba.logging.configure`."""

from __future__ import annotations

import threading

import structlog

from houba.ports.reporter import Counts, ErrorInfo, OperationEvent
from houba.use_cases.report import RunReport


class StructlogReporter:
    def __init__(self) -> None:
        self._log = structlog.get_logger("houba.reconcile")
        self._lock = threading.Lock()

    def run_started(self, policy_count: int, *, mode: str) -> None:
        self._log.info("run.started", policy_count=policy_count, mode=mode)

    def policy_started(self, name: str, source: str) -> None:
        self._log.info("policy.started", policy=name, source=source)

    def operation_applied(self, ev: OperationEvent) -> None:
        # transform_steps/out_digest are only meaningful on applied imported/updated ops;
        # omit them otherwise so copy/skip/alias lines stay terse.
        extra: dict[str, object] = {}
        if ev.transform_steps is not None:
            extra["transform_steps"] = list(ev.transform_steps)
        if ev.out_digest is not None:
            extra["out_digest"] = ev.out_digest
        with self._lock:
            self._log.info(
                "operation",
                policy=ev.policy,
                dest=ev.dest_repo,
                variant=ev.variant,
                kind=ev.kind,
                out_tag=ev.out_tag,
                src_tag=ev.src_tag,
                digest=ev.digest,
                applied=ev.applied,
                **extra,
            )

    def operation_failed(self, ev: OperationEvent, error: ErrorInfo) -> None:
        with self._lock:
            self._log.error(
                "operation.failed",
                policy=ev.policy,
                dest=ev.dest_repo,
                variant=ev.variant,
                kind=ev.kind,
                out_tag=ev.out_tag,
                src_tag=ev.src_tag,
                error_type=error.type,
                error=error.message,
                exit_code=error.exit_code,
            )

    def policy_failed(self, name: str, error: ErrorInfo) -> None:
        self._log.error(
            "policy.failed",
            policy=name,
            error_type=error.type,
            error=error.message,
            exit_code=error.exit_code,
        )

    def policy_completed(self, name: str, totals: Counts) -> None:
        self._log.info(
            "policy.completed",
            policy=name,
            imported=totals.imported,
            updated=totals.updated,
            deleted=totals.deleted,
            aliased=totals.aliased,
            skipped=totals.skipped,
            failed=totals.failed,
        )

    def run_completed(self, report: RunReport) -> None:
        self._log.info(
            "run.completed",
            mode=report.mode,
            status=report.status,
            imported=report.totals.imported,
            updated=report.totals.updated,
            deleted=report.totals.deleted,
            aliased=report.totals.aliased,
            skipped=report.totals.skipped,
            failed=report.totals.failed,
        )
