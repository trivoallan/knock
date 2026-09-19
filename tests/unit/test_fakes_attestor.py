from __future__ import annotations

import pytest

from knock.errors import CosignError
from knock.ports.attestor import VerifiedPredicate
from tests.fakes.attestor import FakeAttestor


def _statement() -> dict:
    return {
        "predicateType": "https://knock.dev/predicate/transform/v1",
        "predicate": {"policy": "p"},
    }


def test_fake_journals_calls_and_returns_ref() -> None:
    fake = FakeAttestor()
    ref = fake.attest("reg/x@sha256:out", _statement())
    assert fake.attested == [("reg/x@sha256:out", _statement())]
    assert ref.predicate_type == "https://knock.dev/predicate/transform/v1"
    assert ref.referrer_digest.startswith("sha256:")


def test_fake_fail_raises_cosign_error() -> None:
    with pytest.raises(CosignError):
        FakeAttestor(fail=True).attest("reg/x@sha256:out", _statement())


def test_fake_attestor_verify_returns_seeded_and_journals():
    pred = VerifiedPredicate(summary={"vuln.high": "0"}, attested_at="2026-06-24T00:00:00+00:00")
    fake = FakeAttestor(predicates=[pred])
    out = fake.verify("reg/app@sha256:abc", "https://knock.dev/predicate/scan/v1")
    assert out == [pred]
    assert fake.verified == [("reg/app@sha256:abc", "https://knock.dev/predicate/scan/v1")]


def test_fake_sign_journals_subject() -> None:
    fake = FakeAttestor()
    fake.sign("reg/x@sha256:out")
    assert fake.signed == ["reg/x@sha256:out"]


def test_fake_verify_signature_returns_seed_and_journals() -> None:
    fake = FakeAttestor(image_signed=True)
    assert fake.verify_signature("reg/x@sha256:out") is True
    assert FakeAttestor().verify_signature("reg/x@sha256:out") is False
    assert fake.signature_verified == ["reg/x@sha256:out"]


def test_fake_fail_raises_on_sign() -> None:
    with pytest.raises(CosignError):
        FakeAttestor(fail=True).sign("reg/x@sha256:out")
