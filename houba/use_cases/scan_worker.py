"""scan_worker — the in-process reserve -> scan -> attach -> ack loop.

Failure routing:
- success          → ack with digest + attest timestamp
- permanent failure → dead_letter (image gone / manifest 404)
- transient failure → do NOTHING; leave the entry pending for the reaper
  (XAUTOCLAIM redelivers it and dead-letters past max_deliveries)

Do NOT call enqueue for retries.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from houba.domain.scan_queue import classify_exception
from houba.ports.queue import QueuePort, Reservation
from houba.use_cases.attach import ScanOutcome, attach_scan


class _Outcome(Protocol):
    subject_digest: str
    timestamp: Any  # datetime


def process_one(
    queue: QueuePort,
    *,
    scan_and_attach: Callable[[str], _Outcome | None],
    max_deliveries: int,
) -> bool:
    """Process at most one reserved ref. Returns False when the queue is empty."""
    res = queue.reserve()
    if res is None:
        return False
    try:
        outcome = scan_and_attach(res.ref)
    except Exception as exc:
        _route(queue, res, classify_exception("attach", type(exc).__name__, str(exc)))
        return True
    if outcome is None:  # no SBOM referrer yet — transient, leave pending
        return True
    queue.ack(res, digest=outcome.subject_digest, attested_at=outcome.timestamp.isoformat())
    return True


def _route(queue: QueuePort, res: Reservation, failure: Any) -> None:
    if failure.kind == "permanent":
        queue.dead_letter(
            res,
            ref=res.ref,
            reason={"kind": failure.kind, "suggested_action": failure.suggested_action},
        )
    # transient: do nothing — the reaper redelivers and eventually dead-letters.


def run_worker(
    queue: QueuePort,
    *,
    scan_and_attach: Callable[[str], _Outcome | None],
    max_deliveries: int = 3,
) -> int:
    """Drain the queue: process entries until reserve() returns None. Returns the
    number handled. KEDA spawns a ScaledJob pod per batch; this drains it and exits."""
    handled = 0
    while process_one(queue, scan_and_attach=scan_and_attach, max_deliveries=max_deliveries):
        handled += 1
    return handled


def make_scan_and_attach(
    *,
    registry: Any,
    clock: Any,
    label_prefix: str,
    sarif_path: str,
    roster: Any = None,
    attestor: Any = None,
) -> Callable[[str], ScanOutcome | None]:
    """Return a scan_and_attach(ref) closure for run_worker.

    Reads the SARIF file the separate scanner step wrote at ``sarif_path``. If the
    file is missing or empty the scanner has not finished yet — returns ``None``
    (transient) so the entry stays pending and is redelivered by the reaper.
    """
    p = Path(sarif_path)  # fixed at factory time; close over it

    def _scan_and_attach(ref: str) -> ScanOutcome | None:
        if not p.exists() or p.stat().st_size == 0:
            return None
        report_bytes = p.read_bytes()
        return attach_scan(
            ref,
            report_bytes,
            registry=registry,
            clock=clock,
            label_prefix=label_prefix,
            roster=roster,
            attestor=attestor,
        )

    return _scan_and_attach
