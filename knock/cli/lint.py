"""The `knock lint` command — offline validation of a policy tree (design D1-D9)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from knock.config import Settings
from knock.errors import ConfigError
from knock.logging import configure
from knock.use_cases.lint import Finding, LintReport, lint_exit_code, lint_policies


def lint(
    directory: Annotated[
        Path,
        typer.Argument(
            help="Policies directory to lint (not the repository root): every .yaml/.yml under it."
        ),
    ],
) -> None:
    """Validate a policy tree offline and report every problem, not just the first.

    Point it at the policies directory, not the repository root. It calls no registry, git
    remote or tool. Levels: N1 (each file loads), N2 (steps, ownership and alias overlaps),
    N3 (references to the configuration; only when KNOCK_REGISTRIES is set).

    With KNOCK_LOG_FORMAT=json, stdout is one JSON document: `apiVersion` (knock.io/v1alpha1),
    `kind` (LintReport), `errors`, `warnings` and `skipped`. Exit 0 when there is no error
    (warnings do not fail), 1 otherwise, 3 on an invalid directory or configuration.
    """
    if not directory.is_dir():
        raise ConfigError(f"not a directory: {directory}")
    settings = Settings()
    configure(format_=settings.log_format, level=settings.log_level)
    report = lint_policies(
        directory,
        roster=settings.registries,
        ca_certs=settings.transform_ca_certs,
        package_mirrors=settings.transform_package_mirrors,
    )
    _render(report, fmt=settings.log_format)
    raise typer.Exit(lint_exit_code(report))


def _line(label: str, finding: Finding) -> str:
    where = finding.path
    if finding.loc:
        where += " " + _loc(finding.loc)
    related = f" (also: {', '.join(finding.related)})" if finding.related else ""
    return f"{label} {where}: {finding.message}{related}\n"


def _loc(loc: list[str | int]) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else part)
    return out


def _render(report: LintReport, *, fmt: str) -> None:
    if fmt == "json":
        sys.stdout.write(report.model_dump_json(by_alias=True) + "\n")
        return
    for s in report.skipped:
        sys.stdout.write(f"skipped: {s.level} ({s.reason})\n")
    for f in report.errors:
        sys.stdout.write(_line("ERROR", f))
    for f in report.warnings:
        sys.stdout.write(_line("WARN", f))
    sys.stdout.write(f"lint  errors={len(report.errors)} warnings={len(report.warnings)}\n")
