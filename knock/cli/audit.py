"""The `knock audit` command — coverage-gap report (roadmap ④)."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from knock.cli._di import build_container
from knock.logging import configure
from knock.use_cases.audit import CoverageReport, audit_coverage, audit_exit_code


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
    signed: Annotated[
        bool,
        typer.Option(
            "--signed", help="Also probe each stamped image for a signed attestation referrer."
        ),
    ] = False,
    fail_on_unsigned: Annotated[
        bool,
        typer.Option(
            "--fail-on-unsigned",
            help="Exit non-zero if any stamped image is unsigned (implies --signed).",
        ),
    ] = False,
    sbom: Annotated[
        bool,
        typer.Option("--sbom", help="Also probe each stamped image for a package SBOM referrer."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            help="Stop after N images — bounded smoke-check / walk benchmark over a slice.",
        ),
    ] = None,
) -> None:
    """Walk the registry and report images that do NOT carry knock's provenance stamp."""
    container = build_container()
    settings = container.settings
    configure(format_=settings.log_format, level=settings.log_level)
    check_signed = signed or fail_on_unsigned  # the gate implies the probe
    check_sbom = sbom
    report = audit_coverage(
        registry=container.registry,
        roster=settings.registries,
        only_registry=registry_name,
        label_prefix=settings.label_prefix,
        check_signed=check_signed,
        check_sbom=check_sbom,
        limit=limit,
    )
    _render(report, fmt=settings.log_format, check_signed=check_signed, check_sbom=check_sbom)
    raise typer.Exit(
        audit_exit_code(
            report, fail_on_uncovered=fail_on_uncovered, fail_on_unsigned=fail_on_unsigned
        )
    )


def _render(report: CoverageReport, *, fmt: str, check_signed: bool, check_sbom: bool) -> None:
    if fmt == "json":
        sys.stdout.write(report.model_dump_json() + "\n")
        return
    # Text: list only the gaps (uncovered, unsigned, no-sbom, read errors); summary carries totals.
    for o in report.outcomes:
        if o.error is not None:
            sys.stdout.write(f"ERROR     {o.image_ref}  {o.error.message}\n")
        elif not o.covered:
            sys.stdout.write(f"UNCOVERED {o.image_ref}\n")
        elif check_signed and o.signed is False:
            sys.stdout.write(f"UNSIGNED  {o.image_ref}\n")
        elif check_sbom and o.sbom is False:
            sys.stdout.write(f"NO-SBOM   {o.image_ref}\n")
    c = report.counts
    signed_part = f"signed={c.signed} unsigned={c.unsigned} " if check_signed else ""
    sbom_part = f"with_sbom={c.with_sbom} without_sbom={c.without_sbom} " if check_sbom else ""
    sys.stdout.write(
        f"\naudit  scanned={c.scanned} covered={c.covered} "
        f"uncovered={c.uncovered} {signed_part}{sbom_part}errored={c.errored}\n"
    )
