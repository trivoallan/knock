"""Port d'accès aux registres sources (lectures via skopeo)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourceImage:
    digest: str
    architecture: str
    os: str


class SourceRegistryPort(Protocol):
    def list_tags(self, image_ref: str) -> list[str]: ...
    def inspect(self, image_ref: str) -> SourceImage: ...
