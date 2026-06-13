"""Hiérarchie d'exceptions et table des exit codes du CLI houba.

Voir spec §6.3.
"""

from __future__ import annotations

__all__ = [
    "AdapterError",
    "BuildkitError",
    "ConfigError",
    "CosignError",
    "DomainError",
    "HoubaError",
    "InternalError",
    "PolicyValidationError",
    "RegctlError",
    "ScanReportError",
    "UnknownFormatError",
    "UsageOracleError",
    "exit_code_for",
]


class HoubaError(Exception):
    """Racine de toutes les erreurs métier/infra du CLI."""


class DomainError(HoubaError):
    """Erreur métier ou de validation (exit 1)."""


class PolicyValidationError(DomainError):
    """`MirrorPolicy` YAML invalid (schema, unknown field, inconsistent spec)."""


class ScanReportError(DomainError):
    """A scan report cannot be parsed, has an unexpected schema, or its subject digest mismatches."""


class UnknownFormatError(DomainError):
    """The scan report format could not be detected and no valid --format was supplied."""


class AdapterError(HoubaError):
    """Erreur infrastructure / dépendance externe (exit 2)."""


class RegctlError(AdapterError):
    """Erreur d'invocation `regctl` (tag ls, inspect, copy, mod, rm)."""


class BuildkitError(AdapterError):
    """Erreur d'invocation `buildctl` (build, push d'image)."""


class CosignError(AdapterError):
    """Erreur d'invocation `cosign` (attest / sign d'attestations DSSE)."""


class UsageOracleError(AdapterError):
    """Erreur d'invocation de l'oracle d'usage (commande externe injoignable / sortie invalide)."""


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
