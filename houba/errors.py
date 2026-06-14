"""Exception hierarchy and exit-code table for the houba CLI.

See spec §6.3.
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
    """Root of all domain/infrastructure errors raised by the CLI."""


class DomainError(HoubaError):
    """Business logic or validation error (exit 1)."""


class PolicyValidationError(DomainError):
    """`MirrorPolicy` YAML invalid (schema, unknown field, inconsistent spec)."""


class ScanReportError(DomainError):
    """Scan report is unparseable, has an unexpected schema, or its subject digest mismatches."""


class UnknownFormatError(DomainError):
    """The scan report format could not be detected and no valid --format was supplied."""


class AdapterError(HoubaError):
    """Infrastructure / external-dependency error (exit 2)."""


class RegctlError(AdapterError):
    """`regctl` invocation error (tag ls, inspect, copy, mod, rm)."""


class BuildkitError(AdapterError):
    """`buildctl` invocation error (image build and push)."""


class CosignError(AdapterError):
    """`cosign` invocation error (attest / sign DSSE attestations)."""


class UsageOracleError(AdapterError):
    """Usage-oracle invocation error (external command unreachable or invalid output)."""


class ConfigError(HoubaError):
    """Invalid or missing configuration (exit 3)."""


class InternalError(HoubaError):
    """Bug, failed assertion, or unexpected condition (exit 4)."""


# Keys must be the root of each branch (siblings with no inheritance relationship).
# `exit_code_for` walks the exception's MRO and takes the first match — the ordering
# of entries in this dict does not matter as long as the keys remain branch roots.
_EXIT_CODES: dict[type[HoubaError], int] = {
    DomainError: 1,
    AdapterError: 2,
    ConfigError: 3,
    InternalError: 4,
}


def exit_code_for(exc: BaseException) -> int:
    """Return the exit code for an exception by walking its MRO.

    Any exception not rooted in `HoubaError` (e.g. `RuntimeError`, `KeyError`)
    is treated as an `InternalError` (exit 4).
    """
    for klass in type(exc).__mro__:
        code = _EXIT_CODES.get(klass)
        if code is not None:
            return code
    return 4
