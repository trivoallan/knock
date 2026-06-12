"""Port d'accès unifié aux registres OCI (via regctl) : lectures + écritures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ImageInfo:
    digest: str  # manifest/index digest of the ref
    created: datetime | None  # image build time (proxy for source freshness)
    annotations: dict[str, str]  # OCI annotations (incl. recorded base.digest on mirror)


class RegistryPort(Protocol):
    def configure_registry(self, host: str, *, tls_verify: bool, ca_cert: str | None) -> None: ...
    def list_tags(self, repo_ref: str) -> list[str]: ...
    def inspect(self, image_ref: str) -> ImageInfo: ...
    def copy(self, src_ref: str, dst_ref: str) -> None: ...
    def annotate(self, image_ref: str, annotations: dict[str, str]) -> None: ...
    def delete_tag(self, image_ref: str) -> None: ...
    def login(self, host: str, *, username: str, password: str, tls_verify: bool) -> None: ...
