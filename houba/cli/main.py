"""Typer entry point for the houba CLI.

See spec §3 and §6.3 (exception → exit-code mapping).
"""

from __future__ import annotations

import importlib.metadata
import sys

import typer
from pydantic import ValidationError
from pydantic_settings import SettingsError

from houba.cli.attach import attach as attach_cmd
from houba.cli.audit import audit as audit_cmd
from houba.cli.gc import gc as gc_cmd
from houba.cli.purge import purge as purge_cmd
from houba.cli.reconcile import reconcile as reconcile_cmd
from houba.cli.scan import scan_app
from houba.cli.verify import verify as verify_cmd
from houba.errors import HoubaError, exit_code_for

app = typer.Typer(name="houba", no_args_is_help=True, add_completion=False)


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
        v = importlib.metadata.version("houba")
    except importlib.metadata.PackageNotFoundError:
        v = "0.1.0-dev"
    typer.echo(v)


def _run() -> None:
    """Entry-point wrapper that maps Houba exceptions to exit codes.

    See spec §6.3:
      1 = DomainError, 2 = AdapterError, 3 = ConfigError, 4 = InternalError.
    Pydantic ValidationError (invalid / missing config) is also mapped to exit 3.
    """
    try:
        app()
    except (ValidationError, SettingsError) as e:
        typer.echo(f"Invalid configuration: {e}", err=True)
        sys.exit(3)
    except HoubaError as e:
        typer.echo(f"{type(e).__name__}: {e}", err=True)
        sys.exit(exit_code_for(e))


if __name__ == "__main__":
    _run()
