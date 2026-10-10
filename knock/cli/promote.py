"""The `knock promote <dir> --staged <file>` command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from knock.cli._di import build_container
from knock.cli.render import render_report
from knock.domain.gate import StagedRebuilds
from knock.errors import ConfigError
from knock.logging import configure
from knock.use_cases.loader import load_policy_dir
from knock.use_cases.promote import promote_staged
from knock.use_cases.report import report_exit_code


def promote(
    directory: Annotated[Path, typer.Argument(help="Directory of MirrorPolicy files (recursive).")],
    staged: Annotated[
        Path,
        typer.Option(
            "--staged",
            help="A filtered StagedRebuilds file (written by `reconcile --staged-out`): "
            "place each entry it still names, and nothing else.",
        ),
    ],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Unfold per-operation detail in text output.")
    ] = False,
    concurrency: Annotated[
        int | None,
        typer.Option(
            "--concurrency",
            "-j",
            min=1,
            help="Max parallel entries (overrides KNOCK_MAX_CONCURRENCY; 1 = sequential).",
        ),
    ] = None,
    report_json: Annotated[
        bool, typer.Option("--report-json", help="Emit the report as JSON to stdout.")
    ] = False,
) -> None:
    """Promote staged rebuilds to their destinations: copy by digest with their evidence,
    verify it arrived, then write the tag and the aliases."""
    container = build_container()
    configure(format_=container.settings.log_format, level=container.settings.log_level)
    try:
        doc = StagedRebuilds.model_validate_json(staged.read_text())
    except (OSError, ValidationError) as exc:
        raise ConfigError(f"--staged {staged}: {exc}") from exc

    report = promote_staged(
        doc,
        load_policy_dir(directory),
        registry=container.registry,
        roster=container.settings.registries,
        label_prefix=container.settings.label_prefix,
        sbom_formats=container.settings.sbom_formats,
        attestor=container.attestor,
        reporter=container.reporter,
        max_concurrency=(
            concurrency if concurrency is not None else container.settings.max_concurrency
        ),
    )
    fmt = "json" if report_json else container.settings.log_format
    render_report(report, fmt=fmt, verbose=verbose, stream=sys.stdout, verb="promote")
    raise typer.Exit(report_exit_code(report))
