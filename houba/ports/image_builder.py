"""OCI image builder port (BuildKit in production)."""

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
    platform: str | None = None
    provenance: bool = False  # enable BuildKit's native SLSA provenance attestation
    tls_verify: bool = True  # False => push over plain HTTP (registry.insecure=true)


class ImageBuilderPort(Protocol):
    def build_and_push(self, request: BuildRequest) -> None: ...
