"""The `houba purge` command — the reference reaper (spec §3)."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from houba.cli._di import build_container, build_usage_oracle
from houba.errors import ConfigError
from houba.logging import configure
from houba.use_cases.purge import PurgeReport, purge_exit_code, purge_marks


def purge(
    registry_name: Annotated[
        str | None,
        typer.Option("--registry", help="Bound the walk to one registry from the roster."),
    ] = None,
    apply: Annotated[
        bool, typer.Option("--apply", help="Actually delete (default: dry-run, plan only).")
    ] = False,
) -> None:
    """Reap pending-deletion marks: purge tags not seen in prod within the idle window."""
    container = build_container()
    settings = container.settings
    configure(format_=settings.log_format, level=settings.log_level)

    if settings.purge_min_idle_days is None:
        raise ConfigError("houba purge requires HOUBA_PURGE_MIN_IDLE_DAYS (idle window in days)")
    oracle = build_usage_oracle(settings)

    # HOUBA_DRY_RUN_DELETIONS is the deployment-wide deletion kill-switch (shared with
    # reconcile): it forces dry-run even when --apply is passed. --apply is the explicit
    # per-invocation gate; the env var is belt-and-suspenders for a destructive command.
    effective_apply = apply and not settings.dry_run_deletions
    report = purge_marks(
        registry=container.registry,
        oracle=oracle,
        roster=settings.registries,
        only_registry=registry_name,
        label_prefix=settings.label_prefix,
        min_idle_days=settings.purge_min_idle_days,
        now=container.clock.now(),
        apply=effective_apply,
    )
    _render(report, fmt=settings.log_format)
    raise typer.Exit(purge_exit_code(report))


def _render(report: PurgeReport, *, fmt: str) -> None:
    if fmt == "json":
        sys.stdout.write(report.model_dump_json() + "\n")
        return
    counts = {"purge": 0, "protect": 0, "uncertain": 0, "error": 0}
    for o in report.outcomes:
        counts["error" if o.error is not None else (o.decision or "uncertain")] += 1
        verb = "ERROR" if o.error is not None else (o.decision or "?").upper()
        applied = " [applied]" if o.applied else ""
        sys.stdout.write(f"{verb:9} {o.image_ref}{applied}  {o.reason}\n")
    sys.stdout.write(
        f"\n[{report.mode}] purge={counts['purge']} protect={counts['protect']} "
        f"uncertain={counts['uncertain']} error={counts['error']}\n"
    )
