"""scan_worker — reserve → scan → attach → ack, split across containers.

The ScaledJob init-container topology means:
  1. ``houba scan reserve``  — reserves one digest and writes token + ref to /shared
  2. [fetch-sbom + grype in separate containers, reading /shared/digest]
  3. ``houba scan attach``   — reads the reservation from /shared, attaches, acks

Failure routing (both halves):
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


def handle_reservation(
    queue: QueuePort,
    res: Reservation,
    *,
    scan_and_attach: Callable[[str], _Outcome | None],
) -> None:
    """Scan-result -> attach -> ack for an already-reserved entry. Success acks;
    a permanent failure dead-letters; a transient failure (incl. missing SARIF)
    is left pending — the reaper redelivers it and dead-letters past max_deliveries."""
    try:
        outcome = scan_and_attach(res.ref)
    except Exception as exc:  # routed via classify, never swallowed
        _route(queue, res, classify_exception("attach", type(exc).__name__, str(exc)))
        return
    if outcome is None:  # no SARIF yet — transient, leave pending
        return
    queue.ack(res, digest=outcome.subject_digest, attested_at=outcome.timestamp.isoformat())


def _route(queue: QueuePort, res: Reservation, failure: Any) -> None:
    if failure.kind == "permanent":
        queue.dead_letter(
            res,
            ref=res.ref,
            reason={"kind": failure.kind, "suggested_action": failure.suggested_action},
        )
    # transient: do nothing — the reaper redelivers and eventually dead-letters.


def make_scan_and_attach(
    *,
    registry: Any,
    clock: Any,
    label_prefix: str,
    sarif_path: str,
    roster: Any = None,
    attestor: Any = None,
) -> Callable[[str], ScanOutcome | None]:
    """Return a scan_and_attach(ref) closure for handle_reservation.

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
