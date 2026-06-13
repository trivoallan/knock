from __future__ import annotations

from houba.ports.attestor import AttestationRef


def test_attestation_ref_is_frozen_value() -> None:
    ref = AttestationRef(predicate_type="https://houba.dev/predicate/transform/v1", referrer_digest="sha256:r")
    assert ref.predicate_type == "https://houba.dev/predicate/transform/v1"
    assert ref.referrer_digest == "sha256:r"
    import dataclasses

    assert dataclasses.is_dataclass(ref)
    try:
        ref.referrer_digest = "x"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover
        raise AssertionError("AttestationRef must be frozen")
