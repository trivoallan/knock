"""The `houba reconcile <dir>` command (copy path)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from houba.cli._di import build_container
from houba.cli.render import render_report
from houba.logging import configure
from houba.use_cases.loader import load_policy_dir
from houba.use_cases.reconcile import reconcile_policies
from houba.use_cases.report import report_exit_code


def reconcile(
    directory: Annotated[Path, typer.Argument(help="Directory of MirrorPolicy files (recursive).")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Plan only — no copies, no deletes.")
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Unfold per-operation detail in text output.")
    ] = False,
    concurrency: Annotated[
        int | None,
        typer.Option(
            "--concurrency",
            "-j",
            min=1,
            help="Max parallel tag operations (overrides HOUBA_MAX_CONCURRENCY; 1 = sequential).",
        ),
    ] = None,
) -> None:
    """Reconcile all MirrorPolicy files under DIRECTORY against their destinations."""
    container = build_container()
    configure(format_=container.settings.log_format, level=container.settings.log_level)

    policies = load_policy_dir(directory)
    report = reconcile_policies(
        policies,
        registry=container.registry,
        builder=container.builder,
        roster=container.settings.registries,
        ca_certs=container.settings.transform_ca_certs,
        package_mirrors=container.settings.transform_package_mirrors,
        build_platform=container.settings.build_platform,
        now=container.clock.now(),
        label_prefix=container.settings.label_prefix,
        dry_run_tags=dry_run or container.settings.dry_run_tags,
        dry_run_deletions=dry_run or container.settings.dry_run_deletions,
        reporter=container.reporter,
        work_dir=container.settings.work_dir,
        max_concurrency=(
            concurrency if concurrency is not None else container.settings.max_concurrency
        ),
    )
    render_report(report, fmt=container.settings.log_format, verbose=verbose, stream=sys.stdout)
    raise typer.Exit(report_exit_code(report))
