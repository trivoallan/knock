from __future__ import annotations

from houba.errors import EolSourceError
from houba.ports.eol_source import EolEntry


class FakeEolSourcePort:
    def __init__(self, *, entries: dict[str, list[EolEntry]] | None = None) -> None:
        self._entries = entries or {}

    def fetch_eol(self, product: str) -> list[EolEntry]:
        try:
            return list(self._entries[product])
        except KeyError as e:
            raise EolSourceError(f"unknown product: {product}") from e
