from __future__ import annotations

from typing import Any

from houba.errors import CosignError
from houba.ports.attestor import AttestationRef


class FakeAttestor:
    def __init__(self, *, fail: bool = False) -> None:
        self.attested: list[tuple[str, dict[str, Any]]] = []
        self._fail = fail

    def attest(self, subject_ref: str, statement: dict[str, Any]) -> AttestationRef:
        if self._fail:
            raise CosignError("fake attestor configured to fail")
        self.attested.append((subject_ref, statement))
        return AttestationRef(
            predicate_type=str(statement.get("predicateType", "")),
            referrer_digest="sha256:fakeattestation",
        )
