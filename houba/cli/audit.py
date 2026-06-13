"""The `houba audit` command — coverage-gap report (roadmap ④)."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from houba.cli._di import build_container
from houba.logging import configure
from houba.use_cases.audit import CoverageReport, audit_coverage, audit_exit_code


def audit(
    registry_name: Annotated[
        str | None,
        typer.Option("--registry", help="Bound the walk to one registry from the roster."),
    ] = None,
    fail_on_uncovered: Annotated[
        bool,
        typer.Option(
            "--fail-on-uncovered", help="Exit non-zero if any image lacks the stamp (CI gate)."
        ),
    ] = False,
) -> None:
    """Walk the registry and report images that do NOT carry houba's provenance stamp."""
    container = build_container()
    settings = container.settings
    configure(format_=settings.log_format, level=settings.log_level)
    report = audit_coverage(
        registry=container.registry,
        roster=settings.registries,
        only_registry=registry_name,
        label_prefix=settings.label_prefix,
    )
    _render(report, fmt=settings.log_format)
    raise typer.Exit(audit_exit_code(report, fail_on_uncovered=fail_on_uncovered))


def _render(report: CoverageReport, *, fmt: str) -> None:
    if fmt == "json":
        sys.stdout.write(report.model_dump_json() + "\n")
        return
    # Text: list only the gaps (uncovered + read errors); the summary line carries the totals.
    for o in report.outcomes:
        if o.error is not None:
            sys.stdout.write(f"ERROR     {o.image_ref}  {o.error.message}\n")
        elif not o.covered:
            sys.stdout.write(f"UNCOVERED {o.image_ref}\n")
    c = report.counts
    sys.stdout.write(
        f"\naudit  scanned={c.scanned} covered={c.covered} "
        f"uncovered={c.uncovered} errored={c.errored}\n"
    )
