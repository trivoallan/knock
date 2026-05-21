"""Point d'entrée Typer de la CLI h2h.

Voir spec §3.
"""

from __future__ import annotations

import importlib.metadata

import typer

from hub2hub.cli import dev as dev_cli

app = typer.Typer(name="h2h", no_args_is_help=True, add_completion=False)
app.add_typer(dev_cli.app, name="dev", help="Outils de développement (capture de fixtures, debug)")


@app.command()
def version() -> None:
    """Affiche la version du CLI."""
    try:
        v = importlib.metadata.version("hub2hub")
    except importlib.metadata.PackageNotFoundError:
        v = "0.1.0-dev"
    typer.echo(v)


if __name__ == "__main__":
    app()
