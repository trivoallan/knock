"""The `knock gc` command — collect superseded scan-result referrers."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from knock.cli._di import build_container
from knock.domain.retention import DEFAULT_KEEP, DEFAULT_OLDER_THAN_DAYS
from knock.logging import configure
from knock.use_cases.gc import GcReport, gc_exit_code, gc_referrers


def gc(
    registry_name: Annotated[
        str | None,
        typer.Option("--registry", help="Bound the walk to one registry from the roster."),
    ] = None,
    keep: Annotated[
        int,
        typer.Option("--keep", help="Newest scan referrers to retain per (tool, format)."),
    ] = DEFAULT_KEEP,
    older_than_days: Annotated[
        int,
        typer.Option("--older-than-days", help="Only collect referrers older than this many days."),
    ] = DEFAULT_OLDER_THAN_DAYS,
    apply: Annotated[
        bool, typer.Option("--apply", help="Actually delete (default: dry-run, plan only).")
    ] = False,
) -> None:
    """Garbage-collect superseded scan-result referrers across the registry roster."""
    container = build_container()
    settings = container.settings
    configure(format_=settings.log_format, level=settings.log_level)

    # KNOCK_DRY_RUN_DELETIONS is the deployment-wide deletion kill-switch (shared with
    # reconcile/purge): it forces dry-run even when --apply is passed.
    effective_apply = apply and not settings.dry_run_deletions
    report = gc_referrers(
        registry=container.registry,
        roster=settings.registries,
        only_registry=registry_name,
        label_prefix=settings.label_prefix,
        keep=keep,
        older_than_days=older_than_days,
        now=container.clock.now(),
        apply=effective_apply,
    )
    _render(report, fmt=settings.log_format)
    raise typer.Exit(gc_exit_code(report))


def _render(report: GcReport, *, fmt: str) -> None:
    if fmt == "json":
        sys.stdout.write(report.model_dump_json() + "\n")
        return
    total_collected = 0
    total_errors = 0
    for o in report.outcomes:
        if o.error is not None:
            total_errors += 1
            sys.stdout.write(f"ERROR    {o.image_ref}  {o.error.type}: {o.error.message}\n")
            continue
        if o.collected:
            total_collected += len(o.collected)
            applied = " [applied]" if o.applied else " (planned)"
            sys.stdout.write(
                f"COLLECT  {o.image_ref}  kept={o.kept} collected={len(o.collected)}{applied}\n"
            )
    sys.stdout.write(f"\n[{report.mode}] collected={total_collected} error={total_errors}\n")
