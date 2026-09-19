from __future__ import annotations

from typing import Any

from knock.errors import CosignError
from knock.ports.attestor import AttestationRef, VerifiedPredicate


class FakeAttestor:
    def __init__(
        self,
        *,
        fail: bool = False,
        predicates: list[VerifiedPredicate] | None = None,
        image_signed: bool = False,
    ) -> None:
        self.attested: list[tuple[str, dict[str, Any]]] = []
        self.verified: list[tuple[str, str]] = []
        self.signed: list[str] = []
        self.signature_verified: list[str] = []
        self._image_signed = image_signed
        self._fail = fail
        self._predicates = predicates or []

    def attest(self, subject_ref: str, statement: dict[str, Any]) -> AttestationRef:
        if self._fail:
            raise CosignError("fake attestor configured to fail")
        self.attested.append((subject_ref, statement))
        return AttestationRef(
            predicate_type=str(statement.get("predicateType", "")),
            referrer_digest="sha256:fakeattestation",
        )

    def verify(self, subject_ref: str, predicate_type: str) -> list[VerifiedPredicate]:
        if self._fail:
            raise CosignError("fake attestor configured to fail")
        self.verified.append((subject_ref, predicate_type))
        return list(self._predicates)

    def sign(self, subject_ref: str) -> None:
        if self._fail:
            raise CosignError("fake attestor configured to fail")
        self.signed.append(subject_ref)

    def verify_signature(self, subject_ref: str) -> bool:
        if self._fail:
            raise CosignError("fake attestor configured to fail")
        self.signature_verified.append(subject_ref)
        return self._image_signed
