"""Sous-groupe de commandes internes (dev / debug)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from hub2hub.cli._di import build_container

app = typer.Typer(name="dev", help="Outils de développement (capture de fixtures, debug)")


@app.callback()
def _root() -> None:
    """Sous-groupe de commandes internes."""


@app.command("capture")
def capture(
    project: Annotated[str, typer.Option("--project", help="Nom du projet Harbor")],
    repository: Annotated[
        str, typer.Option("--repository", help="Nom du repository (sans le projet)")
    ],
    output: Annotated[
        Path, typer.Option("--output", help="Répertoire de sortie pour les fixtures")
    ],
) -> None:
    """Capture en read-only l'état Harbor d'un repo dans des fichiers JSON.

    Produit :
      <output>/<project>__repositories.json
      <output>/<project>__<repo-sanitisé>__artifacts.json
    """
    output.mkdir(parents=True, exist_ok=True)
    container = build_container()

    repos = container.harbor.get_repositories(project)
    arts = container.harbor.get_artifacts(project, repository)

    repos_path = output / f"{project}__repositories.json"
    repos_path.write_text(json.dumps([asdict(r) for r in repos], indent=2))

    sanitized = repository.replace("/", "_")
    arts_path = output / f"{project}__{sanitized}__artifacts.json"
    arts_path.write_text(json.dumps([asdict(a) for a in arts], indent=2))

    typer.echo(f"Wrote {repos_path}")
    typer.echo(f"Wrote {arts_path}")
