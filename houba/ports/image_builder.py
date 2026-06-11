"""Port d'accès à un builder d'images OCI (BuildKit en prod)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class BuildRequest:
    dockerfile_path: Path
    context_dir: Path
    image_ref: str
    build_args: dict[str, str] = field(default_factory=dict)


class ImageBuilderPort(Protocol):
    def build_and_push(self, request: BuildRequest) -> None: ...
