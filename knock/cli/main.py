"""Typer entry point for the knock CLI.

See spec §3 and §6.3 (exception → exit-code mapping).
"""

from __future__ import annotations

import importlib.metadata
import sys

import typer
from pydantic import ValidationError
from pydantic_settings import SettingsError

from knock.cli.attach import attach as attach_cmd
from knock.cli.audit import audit as audit_cmd
from knock.cli.gc import gc as gc_cmd
from knock.cli.purge import purge as purge_cmd
from knock.cli.reconcile import reconcile as reconcile_cmd
from knock.cli.scan import scan_app
from knock.cli.verify import verify as verify_cmd
from knock.errors import KnockError, exit_code_for

app = typer.Typer(name="knock", no_args_is_help=True, add_completion=False)


app.command(name="reconcile")(reconcile_cmd)
app.command(name="purge")(purge_cmd)
app.command(name="attach")(attach_cmd)
app.command(name="audit")(audit_cmd)
app.command(name="gc")(gc_cmd)
app.command(name="verify")(verify_cmd)
app.add_typer(scan_app, name="scan")


@app.command()
def version() -> None:
    """Print the CLI version."""
    try:
        v = importlib.metadata.version("knock-oci")
    except importlib.metadata.PackageNotFoundError:
        v = "0.1.0-dev"
    typer.echo(v)


def _run() -> None:
    """Entry-point wrapper that maps Knock exceptions to exit codes.

    See spec §6.3:
      1 = DomainError, 2 = AdapterError, 3 = ConfigError, 4 = InternalError.
    Pydantic ValidationError (invalid / missing config) is also mapped to exit 3.
    """
    try:
        app()
    except (ValidationError, SettingsError) as e:
        typer.echo(f"Invalid configuration: {e}", err=True)
        sys.exit(3)
    except KnockError as e:
        typer.echo(f"{type(e).__name__}: {e}", err=True)
        sys.exit(exit_code_for(e))


if __name__ == "__main__":
    _run()
