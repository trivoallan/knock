"""The `houba attach <ref> --report <file|->` command (ingest + stamp a scan result)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from houba.cli._di import build_container
from houba.cli.render import render_scan_outcome
from houba.domain.scan.summary import Severity, gate_breached
from houba.logging import configure
from houba.use_cases.attach import attach_exit_code, attach_scan


def attach(
    image_ref: Annotated[str, typer.Argument(help="Image reference (tag or digest) to stamp.")],
    report: Annotated[
        str, typer.Option("--report", help="Path to the upstream scan report, or '-' for stdin.")
    ],
    format_: Annotated[
        str | None,
        typer.Option("--format", help="Override report-format auto-detection (e.g. 'sarif')."),
    ] = None,
    output: Annotated[
        str, typer.Option("--output", help="Output format: 'text' (default) or 'json'.")
    ] = "text",
    fail_on: Annotated[
        Severity | None,
        typer.Option(
            "--fail-on",
            help="Exit non-zero if the scan has a finding at or above this severity (CI gate).",
        ),
    ] = None,
) -> None:
    """Ingest a scan report produced upstream and attach it as a stamped OCI referrer."""
    container = build_container()
    configure(format_=container.settings.log_format, level=container.settings.log_level)

    report_bytes = sys.stdin.buffer.read() if report == "-" else Path(report).read_bytes()
    outcome = attach_scan(
        image_ref,
        report_bytes,
        registry=container.registry,
        clock=container.clock,
        label_prefix=container.settings.label_prefix,
        format_override=format_,
        attestor=container.attestor,
        builder_id=container.settings.attest_builder_id,
    )
    render_scan_outcome(outcome, fmt=output, stream=sys.stdout)
    if fail_on is not None and gate_breached(outcome.facts, fail_on):
        sys.stderr.write(f"gating: scan has a finding at or above {fail_on.value} (--fail-on)\n")
    raise typer.Exit(attach_exit_code(outcome, fail_on=fail_on))
