"""Port for signing + attaching an in-toto attestation as an OCI referrer.

The domain builds the Statement (pure, `domain/attestation.py`); this port signs it
(DSSE) and attaches it to the subject digest. Like every port: a typing.Protocol +
a frozen data model, never importing from houba.adapters.*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AttestationRef:
    predicate_type: str  # the predicateType that was attested
    referrer_digest: str  # the attestation manifest digest, best-effort ("" if unknown)


class AttestorPort(Protocol):
    def attest(self, subject_ref: str, statement: dict[str, Any]) -> AttestationRef:
        """Sign `statement` (DSSE) and attach it as a referrer to `subject_ref`."""
        ...
