"""Hiérarchie d'exceptions et table des exit codes du CLI h2h.

Voir spec §6.3.
"""

from __future__ import annotations

__all__ = [
    "AdapterError",
    "BuildkitError",
    "ConfigError",
    "DomainError",
    "EolDateInconsistencyError",
    "EolSourceError",
    "GitError",
    "GitLabError",
    "H2HError",
    "HarborAuthError",
    "HarborError",
    "HarborNotFoundError",
    "HarborTransientError",
    "InternalError",
    "NoTagsToImportError",
    "PropertiesValidationError",
    "SkopeoError",
    "exit_code_for",
]


class H2HError(Exception):
    """Racine de toutes les erreurs métier/infra du CLI."""


class DomainError(H2HError):
    """Erreur métier ou de validation (exit 1)."""


class PropertiesValidationError(DomainError):
    """`properties.yml` invalide (schéma, regex malformée, valeur inattendue)."""


class NoTagsToImportError(DomainError):
    """Aucun tag source ne satisfait les filtres après application du calcul."""


class EolDateInconsistencyError(DomainError):
    """La donnée EOL récupérée pour le produit est incohérente avec le tag traité."""


class AdapterError(H2HError):
    """Erreur infrastructure / dépendance externe (exit 2)."""


class HarborError(AdapterError):
    """Erreur de communication ou de protocole avec Harbor."""


class HarborAuthError(HarborError):
    """Échec d'authentification Harbor (HTTP 401 / 403)."""


class HarborNotFoundError(HarborError):
    """Ressource Harbor absente (HTTP 404)."""


class HarborTransientError(HarborError):
    """Erreur transitoire Harbor (5xx, timeout) — éligible au retry."""


class GitError(AdapterError):
    """Erreur d'invocation `git` (clone, commit, push)."""


class SkopeoError(AdapterError):
    """Erreur d'invocation `skopeo` (inspect, list-tags, copy)."""


class BuildkitError(AdapterError):
    """Erreur d'invocation `buildctl` (build, push d'image)."""


class GitLabError(AdapterError):
    """Erreur de communication avec l'API REST GitLab."""


class EolSourceError(AdapterError):
    """Erreur de récupération des données EOL (endoflife.date)."""


class ConfigError(H2HError):
    """Configuration invalide / manquante (exit 3)."""


class InternalError(H2HError):
    """Bug, assertion, condition inattendue (exit 4)."""


# Les clés doivent être les racines de chaque branche (siblings non liées par héritage).
# `exit_code_for` parcourt la MRO de l'exception et prend le premier match — l'ordre des
# entrées de ce dict n'a pas d'importance tant que les clés restent des branches racines.
_EXIT_CODES: dict[type[H2HError], int] = {
    DomainError: 1,
    AdapterError: 2,
    ConfigError: 3,
    InternalError: 4,
}


def exit_code_for(exc: BaseException) -> int:
    """Retourne l'exit code pour une exception en parcourant sa MRO.

    Toute exception non rattachée à `H2HError` (ex. `RuntimeError`, `KeyError`)
    est traitée comme une `InternalError` (exit 4).
    """
    for klass in type(exc).__mro__:
        code = _EXIT_CODES.get(klass)
        if code is not None:
            return code
    return 4
