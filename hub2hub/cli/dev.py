from __future__ import annotations

import typer

app = typer.Typer(name="dev", help="Outils de développement (capture de fixtures, debug)")


@app.callback()
def _root() -> None:
    """Sous-groupe de commandes internes."""
