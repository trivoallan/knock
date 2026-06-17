"""Port: generate package-level SBOM(s) for an already-placed image, by digest.

The domain maps formats to media types and builds the referrer annotations
(`domain/sbom.py`); this port produces the SBOM bytes. Like every port: a
typing.Protocol + a frozen data model, never importing from houba.adapters.*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SbomDocument:
    format: str  # syft output name, e.g. "spdx-json" / "cyclonedx-json"
    media_type: str  # OCI media type, e.g. "application/spdx+json"
    content: bytes  # the serialized SBOM
    tool_version: str = ""  # producing syft version, e.g. "1.20.0" ("" if unknown)


class SbomGeneratorPort(Protocol):
    def generate(
        self,
        image_ref: str,
        formats: list[str],
        *,
        tls_verify: bool = True,
        username: str | None = None,
        password: str | None = None,
        ca_cert: str | None = None,
    ) -> list[SbomDocument]:
        """Scan `image_ref` (a digest-pinned ref) and return one document per format.

        One scan, N outputs. Auth/TLS describe the registry `image_ref` lives in.
        """
        ...
