"""The `houba scan` sub-app — platform scan-pipeline commands.

Redis is an optional dependency (``pip install houba[scan]``).  Top-level imports
are stdlib + typer ONLY so that ``houba scan --help`` works without redis-py.
Commands that actually need Redis call ``_adapter()`` which imports lazily.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import typer

scan_app = typer.Typer(
    name="scan",
    no_args_is_help=True,
    help="Platform scan-pipeline commands (requires `pip install houba[scan]`).",
)


def _adapter() -> Any:
    """Lazily import redis and build the RedisStreamsAdapter.

    Prints a friendly install hint and exits 3 when redis-py is absent.
    """
    try:
        import redis  # noqa: F401
    except ModuleNotFoundError:
        typer.echo("pip install houba[scan] (redis-py is not installed)", err=True)
        raise typer.Exit(code=3) from None
    from houba.cli._di import build_scan_adapter

    return build_scan_adapter()


@scan_app.command()
def reserve() -> None:
    """Reserve one placed digest from the queue and write it to /shared for the
    scanner + attach steps. Exits 75 (EX_TEMPFAIL) when the queue is empty."""
    res = _adapter().reserve()
    if res is None:
        typer.echo("scan queue empty", err=True)
        raise typer.Exit(code=75)
    Path(os.environ.get("HOUBA_SCAN_DIGEST_PATH", "/shared/digest")).write_text(res.ref)
    Path(os.environ.get("HOUBA_SCAN_TOKEN_PATH", "/shared/reservation-token")).write_text(
        res.token
    )
    typer.echo(res.ref)


@scan_app.command()
def attach() -> None:
    """Read the reserved digest + the scanner's SARIF, attach the result, and ack.
    A missing/empty SARIF or a transient failure leaves the entry pending (the
    reaper retries); a permanent failure dead-letters it."""
    from houba.cli._di import build_scan_and_attach
    from houba.ports.queue import Reservation
    from houba.use_cases.scan_worker import handle_reservation

    ref = (
        Path(os.environ.get("HOUBA_SCAN_DIGEST_PATH", "/shared/digest")).read_text().strip()
    )
    token = (
        Path(os.environ.get("HOUBA_SCAN_TOKEN_PATH", "/shared/reservation-token"))
        .read_text()
        .strip()
    )
    res = Reservation(token=token, ref=ref)
    handle_reservation(_adapter(), res, scan_and_attach=build_scan_and_attach())


@scan_app.command()
def enqueue() -> None:
    """Read a reconcile JSON report from stdin and enqueue the placed image refs."""
    from houba.domain.scan_queue import enqueue_refs

    report = json.load(sys.stdin)
    adapter = _adapter()
    refs = enqueue_refs(report)
    adapter.enqueue(refs)
    typer.echo(f"enqueued {len(refs)} ref(s)")


@scan_app.command()
def reaper(
    min_idle_ms: int = typer.Option(600_000, "--min-idle-ms", help="Idle threshold in ms."),
    max_deliveries: int = typer.Option(3, "--max-deliveries", help="Dead-letter threshold."),
) -> None:
    """Claim idle entries and route past-threshold ones to the dead stream."""
    adapter = _adapter()
    claimed = adapter.reaper(min_idle_ms=min_idle_ms, max_deliveries=max_deliveries)
    typer.echo(f"reaper: claimed {len(claimed)} entr{'y' if len(claimed) == 1 else 'ies'}")
