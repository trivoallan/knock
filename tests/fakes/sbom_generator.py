from __future__ import annotations

from knock.domain.sbom import media_type_for
from knock.errors import SyftError
from knock.ports.sbom import SbomDocument

FAKE_SYFT_VERSION = "9.9.9-fake"


class FakeSbomGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        # journal: (image_ref, formats, tls_verify) per call
        self.calls: list[tuple[str, tuple[str, ...], bool]] = []
        self._fail = fail

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
        if self._fail:
            raise SyftError("fake syft configured to fail")
        self.calls.append((image_ref, tuple(formats), tls_verify))
        return [
            SbomDocument(
                format=f,
                media_type=media_type_for(f),
                content=f'{{"sbom":"{f}"}}'.encode(),
                tool_version=FAKE_SYFT_VERSION,
            )
            for f in formats
        ]
