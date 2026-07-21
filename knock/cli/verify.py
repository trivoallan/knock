"""The `knock verify <ref>` command — read-only gate over knock's referrers."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from knock.cli._di import build_container
from knock.cli.render import render_verify_report
from knock.domain.scan.summary import Severity
from knock.domain.verify import parse_duration, parse_requirements
from knock.logging import configure
from knock.use_cases.verify import verify_exit_code, verify_image


def verify(
    image_ref: Annotated[str, typer.Argument(help="Image reference (tag or digest) to verify.")],
    require: Annotated[
        str, typer.Option("--require", help="Comma-separated: scan-pass,stamp,sbom.")
    ] = "scan-pass",
    max_severity: Annotated[
        Severity, typer.Option("--max-severity", help="Fail at or above this scan severity.")
    ] = Severity.high,
    max_age: Annotated[
        str, typer.Option("--max-age", help="Scan freshness SLA (e.g. 7d, 12h, 30m).")
    ] = "7d",
    registry_name: Annotated[
        str | None, typer.Option("--registry", help="Roster entry to authenticate against.")
    ] = None,
    output: Annotated[
        str, typer.Option("--output", help="Output format: 'text' (default) or 'json'.")
    ] = "text",
) -> None:
    """Read knock's facts for a digest and gate on them (exit 0 = pass, 1 = fail)."""
    container = build_container()
    configure(format_=container.settings.log_format, level=container.settings.log_level)
    report = verify_image(
        image_ref,
        requirements=parse_requirements(require),
        registry=container.registry,
        attestor=container.attestor,
        clock=container.clock,
        label_prefix=container.settings.label_prefix,
        max_severity=max_severity,
        max_age=parse_duration(max_age),
        roster=container.settings.registries,
        registry_override=registry_name,
    )
    render_verify_report(report, fmt=output, stream=sys.stdout)
    raise typer.Exit(verify_exit_code(report))
