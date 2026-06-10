"""Hiérarchie d'exceptions et table des exit codes du CLI houba.

Voir spec §6.3.
"""

from __future__ import annotations

__all__ = [
    "AdapterError",
    "BuildkitError",
    "ConfigError",
    "DomainError",
    "GitError",
    "GitLabError",
    "HarborAuthError",
    "HarborError",
    "HarborNotFoundError",
    "HarborTransientError",
    "HoubaError",
    "InternalError",
    "NoTagsToImportError",
    "PolicyValidationError",
    "PropertiesValidationError",
    "SkopeoError",
    "exit_code_for",
]


class HoubaError(Exception):
    """Racine de toutes les erreurs métier/infra du CLI."""


class DomainError(HoubaError):
    """Erreur métier ou de validation (exit 1)."""


class PropertiesValidationError(DomainError):
    """`properties.yml` invalide (schéma, regex malformée, valeur inattendue)."""


class PolicyValidationError(DomainError):
    """`MirrorPolicy` YAML invalid (schema, unknown field, inconsistent spec)."""


class NoTagsToImportError(DomainError):
    """Aucun tag source ne satisfait les filtres après application du calcul."""


class AdapterError(HoubaError):
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


class ConfigError(HoubaError):
    """Configuration invalide / manquante (exit 3)."""


class InternalError(HoubaError):
    """Bug, assertion, condition inattendue (exit 4)."""


# Les clés doivent être les racines de chaque branche (siblings non liées par héritage).
# `exit_code_for` parcourt la MRO de l'exception et prend le premier match — l'ordre des
# entrées de ce dict n'a pas d'importance tant que les clés restent des branches racines.
_EXIT_CODES: dict[type[HoubaError], int] = {
    DomainError: 1,
    AdapterError: 2,
    ConfigError: 3,
    InternalError: 4,
}


def exit_code_for(exc: BaseException) -> int:
    """Retourne l'exit code pour une exception en parcourant sa MRO.

    Toute exception non rattachée à `HoubaError` (ex. `RuntimeError`, `KeyError`)
    est traitée comme une `InternalError` (exit 4).
    """
    for klass in type(exc).__mro__:
        code = _EXIT_CODES.get(klass)
        if code is not None:
            return code
    return 4
