"""The `houba reconcile <dir>` command (copy path)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from houba.cli._di import build_container
from houba.use_cases.loader import load_policy_dir
from houba.use_cases.reconcile import reconcile_policies


def reconcile(
    directory: Annotated[Path, typer.Argument(help="Directory of MirrorPolicy files (recursive).")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Plan only — no copies, no deletes.")
    ] = False,
) -> None:
    """Reconcile all MirrorPolicy files under DIRECTORY against their destinations."""
    container = build_container()
    policies = load_policy_dir(directory)
    summary = reconcile_policies(
        policies,
        registry=container.registry,
        roster=container.settings.registries,
        now=container.clock.now(),
        label_prefix=container.settings.label_prefix,
        dry_run_tags=dry_run or container.settings.dry_run_tags,
        dry_run_deletions=dry_run or container.settings.dry_run_deletions,
    )
    typer.echo(
        f"reconcile: imported={summary.imported} updated={summary.updated} "
        f"deleted={summary.deleted} aliased={summary.aliased}"
    )
