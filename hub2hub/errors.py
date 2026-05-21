"""Hiérarchie d'exceptions et table des exit codes du CLI h2h.

Voir spec §6.3.
"""

from __future__ import annotations


class H2HError(Exception):
    """Racine de toutes les erreurs métier/infra du CLI."""


class DomainError(H2HError):
    """Erreur métier ou de validation (exit 1)."""


class PropertiesValidationError(DomainError):
    pass


class NoTagsToImportError(DomainError):
    pass


class EolDateInconsistencyError(DomainError):
    pass


class AdapterError(H2HError):
    """Erreur infrastructure / dépendance externe (exit 2)."""


class HarborError(AdapterError):
    pass


class HarborAuthError(HarborError):
    pass


class HarborNotFoundError(HarborError):
    pass


class HarborTransientError(HarborError):
    pass


class GitError(AdapterError):
    pass


class SkopeoError(AdapterError):
    pass


class BuildkitError(AdapterError):
    pass


class GitLabError(AdapterError):
    pass


class EolSourceError(AdapterError):
    pass


class ConfigError(H2HError):
    """Configuration invalide / manquante (exit 3)."""


class InternalError(H2HError):
    """Bug, assertion, condition inattendue (exit 4)."""


_EXIT_CODES: dict[type[H2HError], int] = {
    DomainError: 1,
    AdapterError: 2,
    ConfigError: 3,
    InternalError: 4,
}


def exit_code_for(exc: BaseException) -> int:
    """Retourne l'exit code pour une exception.

    Toute exception inconnue est traitée comme une InternalError (exit 4).
    """
    for base, code in _EXIT_CODES.items():
        if isinstance(exc, base):
            return code
    return 4
