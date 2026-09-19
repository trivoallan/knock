"""Port for signing + attaching an in-toto attestation as an OCI referrer, and for
signing the image itself at admission.

The domain builds the Statement (pure, `domain/attestation.py`); this port signs it
(DSSE) and attaches it to the subject digest. Like every port: a typing.Protocol +
a frozen data model, never importing from knock.adapters.*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AttestationRef:
    predicate_type: str  # the predicateType that was attested
    referrer_digest: str  # the attestation manifest digest, best-effort ("" if unknown)


@dataclass(frozen=True)
class VerifiedPredicate:
    """A signature-verified scan predicate (the trustworthy form read back from a referrer)."""

    summary: dict[str, str]  # prefix-less io.knock.scan.* facts, incl. vuln.<bucket> counts
    attested_at: str  # ISO-8601; the signed freshness clock


class AttestorPort(Protocol):
    def attest(self, subject_ref: str, statement: dict[str, Any]) -> AttestationRef:
        """Sign `statement` (DSSE) and attach it as a referrer to `subject_ref`."""
        ...

    def verify(self, subject_ref: str, predicate_type: str) -> list[VerifiedPredicate]:
        """Return the signature-verified predicates of `predicate_type` on `subject_ref`.

        Empty list = cosign ran but found no verifiable attestation (fail-closed at the gate).
        Raises only when cosign cannot run.
        """
        ...

    def sign(self, subject_ref: str) -> None:
        """Sign the image `subject_ref` itself (not a predicate) — the act of admission."""
        ...

    def verify_signature(self, subject_ref: str) -> bool:
        """True iff `subject_ref` carries a verified *image* signature.

        An attestation alone must not count (cosign v3 stores both as the same bundle type).
        False = cosign ran, nothing verifiable (fail-closed). Raises only when cosign cannot run.
        """
        ...
