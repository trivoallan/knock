"""The built-in scan-format registry. Explicit tuple, no import-time side effects."""

from __future__ import annotations

from knock.domain.scan.formats.base import ScanFormatMapper
from knock.domain.scan.formats.sarif import SarifMapper
from knock.errors import UnknownFormatError

# v1: SARIF only. Trivy-native / CycloneDX / EOL mappers drop in here, no other change.
BUILTIN_FORMATS: tuple[ScanFormatMapper, ...] = (SarifMapper(),)


class Registry:
    def __init__(self, mappers: tuple[ScanFormatMapper, ...]) -> None:
        self._by_name: dict[str, ScanFormatMapper] = {m.name: m for m in mappers}

    def get(self, name: str) -> ScanFormatMapper:
        try:
            return self._by_name[name]
        except KeyError:
            raise UnknownFormatError(
                f"unknown scan format {name!r}; allowed: {sorted(self._by_name)}"
            ) from None

    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def mappers(self) -> tuple[ScanFormatMapper, ...]:
        return tuple(self._by_name.values())


DEFAULT_REGISTRY = Registry(BUILTIN_FORMATS)
