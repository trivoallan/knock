"""Sous-groupe de commandes internes (dev / debug)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from hub2hub.cli._di import build_container

app = typer.Typer(name="dev", help="Outils de développement (capture de fixtures, debug)")

# Caractères acceptés dans un segment de nom de fichier dérivé d'un projet ou
# repository Harbor. Le but est de bloquer toute composante path-traversal
# (`..`, `/`, `\`) ou exotique avant interpolation dans un nom de fichier.
_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_segment(name: str) -> str:
    """Convertit un identifiant Harbor en composante de nom de fichier sûre."""
    cleaned = _SAFE_SEGMENT_RE.sub("_", name).strip("._")
    return cleaned or "_"


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
      <output>/<project-sanitisé>__repositories.json
      <output>/<project-sanitisé>__<repo-sanitisé>__artifacts.json
    """
    # Construire le container avant de toucher au filesystem : si la config est
    # invalide, on échoue avant de créer un répertoire inutile.
    container = build_container()
    output.mkdir(parents=True, exist_ok=True)

    repos = container.harbor.get_repositories(project)
    arts = container.harbor.get_artifacts(project, repository)

    project_safe = _sanitize_segment(project)
    repo_safe = _sanitize_segment(repository)

    repos_path = output / f"{project_safe}__repositories.json"
    repos_path.write_text(json.dumps([asdict(r) for r in repos], indent=2))

    arts_path = output / f"{project_safe}__{repo_safe}__artifacts.json"
    arts_path.write_text(json.dumps([asdict(a) for a in arts], indent=2))

    typer.echo(f"Wrote {repos_path}")
    typer.echo(f"Wrote {arts_path}")
