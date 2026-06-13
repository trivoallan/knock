"""Point d'entrée Typer de la CLI houba.

Voir spec §3 et §6.3 (mapping exception → exit code).
"""

from __future__ import annotations

import importlib.metadata
import sys

import typer
from pydantic import ValidationError
from pydantic_settings import SettingsError

from houba.cli.attach import attach as attach_cmd
from houba.cli.purge import purge as purge_cmd
from houba.cli.reconcile import reconcile as reconcile_cmd
from houba.errors import HoubaError, exit_code_for

app = typer.Typer(name="houba", no_args_is_help=True, add_completion=False)


app.command(name="reconcile")(reconcile_cmd)
app.command(name="purge")(purge_cmd)
app.command(name="attach")(attach_cmd)


@app.command()
def version() -> None:
    """Affiche la version du CLI."""
    try:
        v = importlib.metadata.version("houba")
    except importlib.metadata.PackageNotFoundError:
        v = "0.1.0-dev"
    typer.echo(v)


def _run() -> None:
    """Wrapper d'entrée qui mappe les exceptions Houba sur des exit codes.

    Voir spec §6.3 :
      1 = DomainError, 2 = AdapterError, 3 = ConfigError, 4 = InternalError.
    Les ValidationError de Pydantic (config invalide / manquante) sont
    également mappées sur exit 3.
    """
    try:
        app()
    except (ValidationError, SettingsError) as e:
        typer.echo(f"Configuration invalide : {e}", err=True)
        sys.exit(3)
    except HoubaError as e:
        typer.echo(f"{type(e).__name__}: {e}", err=True)
        sys.exit(exit_code_for(e))


if __name__ == "__main__":
    _run()
