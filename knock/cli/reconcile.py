"""The `knock reconcile <dir>` command (copy path)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from knock.cli._di import build_container
from knock.cli.render import render_report
from knock.domain.gate import Gate, ReconcilePlan
from knock.errors import ConfigError
from knock.logging import configure
from knock.use_cases.loader import load_policy_dir
from knock.use_cases.reconcile import reconcile_policies
from knock.use_cases.report import report_exit_code


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
            help="Max parallel tag operations (overrides KNOCK_MAX_CONCURRENCY; 1 = sequential).",
        ),
    ] = None,
    shard_index: Annotated[
        int,
        typer.Option(
            "--shard-index",
            min=0,
            help="This shard's 0-based index (pass $JOB_COMPLETION_INDEX in an Indexed Job).",
        ),
    ] = 0,
    shard_count: Annotated[
        int,
        typer.Option("--shard-count", min=1, help="Total shards N (1 = process all policies)."),
    ] = 1,
    report_json: Annotated[
        bool,
        typer.Option(
            "--report-json",
            help="Emit the reconcile report as JSON to stdout (for piping to `knock scan enqueue`).",  # noqa: E501
        ),
    ] = False,
    plan_out: Annotated[
        Path | None,
        typer.Option(
            "--plan-out",
            help="Gate, step 1: place nothing, write every import/update/rebuild the run "
            "would perform to FILE (a ReconcilePlan) for an external evaluator.",
        ),
    ] = None,
    apply_plan: Annotated[
        Path | None,
        typer.Option(
            "--apply-plan",
            help="Gate, step 2: reconcile, but apply an import/update/rebuild only if FILE "
            "(a filtered ReconcilePlan) still names it; report the others as withheld.",
        ),
    ] = None,
) -> None:
    """Reconcile all MirrorPolicy files under DIRECTORY against their destinations."""
    container = build_container()
    configure(format_=container.settings.log_format, level=container.settings.log_level)

    if shard_index >= shard_count:
        raise ConfigError(f"--shard-index ({shard_index}) must be < --shard-count ({shard_count})")

    if plan_out is not None and apply_plan is not None:
        raise ConfigError("--plan-out and --apply-plan are exclusive")
    gate: Gate | None = Gate() if plan_out is not None else None
    if apply_plan is not None:
        try:
            gate = Gate.from_plan(ReconcilePlan.model_validate_json(apply_plan.read_text()))
        except (OSError, ValidationError) as exc:
            raise ConfigError(f"--apply-plan {apply_plan}: {exc}") from exc
    dry_run = dry_run or plan_out is not None  # writing the plan places nothing

    policies = load_policy_dir(directory)
    report = reconcile_policies(
        policies,
        registry=container.registry,
        builder=container.builder,
        source=container.source,
        archiver=container.archiver,
        roster=container.settings.registries,
        ca_certs=container.settings.transform_ca_certs,
        package_mirrors=container.settings.transform_package_mirrors,
        build_platform=container.settings.build_platform,
        now=container.clock.now(),
        label_prefix=container.settings.label_prefix,
        dry_run_tags=dry_run or container.settings.dry_run_tags,
        dry_run_deletions=dry_run or container.settings.dry_run_deletions,
        deletion_mode=container.settings.deletion_mode,
        retention_global=container.settings.retention,
        reporter=container.reporter,
        work_dir=container.settings.work_dir,
        max_concurrency=(
            concurrency if concurrency is not None else container.settings.max_concurrency
        ),
        shard_index=shard_index,
        shard_count=shard_count,
        attestor=container.attestor,
        attest_builder_id=container.settings.attest_builder_id,
        sbom_generator=container.sbom_generator,
        sbom_formats=container.settings.sbom_formats,
        gate=gate,
    )
    if plan_out is not None:
        assert gate is not None
        plan = ReconcilePlan(operations=gate.planned)
        plan_out.write_text(plan.model_dump_json(by_alias=True, indent=2) + "\n")
    fmt = "json" if report_json else container.settings.log_format
    render_report(report, fmt=fmt, verbose=verbose, stream=sys.stdout)
    raise typer.Exit(report_exit_code(report))
