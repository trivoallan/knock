"""Point d'entrée Typer de la CLI houba.

Voir spec §3 et §6.3 (mapping exception → exit code).
"""

from __future__ import annotations

import importlib.metadata

import typer
from pydantic import ValidationError
from pydantic_settings import SettingsError

from houba.cli import dev as dev_cli
from houba.cli.reconcile import reconcile as reconcile_cmd
from houba.errors import HoubaError, exit_code_for

app = typer.Typer(name="houba", no_args_is_help=True, add_completion=False)
app.add_typer(dev_cli.app, name="dev", help="Outils de développement (capture de fixtures, debug)")


app.command(name="reconcile")(reconcile_cmd)


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
        raise typer.Exit(3) from e
    except HoubaError as e:
        code = exit_code_for(e)
        typer.echo(f"{type(e).__name__}: {e}", err=True)
        raise typer.Exit(code) from e


if __name__ == "__main__":
    _run()
