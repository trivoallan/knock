from __future__ import annotations

import pytest

from houba.errors import CosignError
from tests.fakes.attestor import FakeAttestor


def _statement() -> dict:
    return {
        "predicateType": "https://houba.dev/predicate/transform/v1",
        "predicate": {"policy": "p"},
    }


def test_fake_journals_calls_and_returns_ref() -> None:
    fake = FakeAttestor()
    ref = fake.attest("reg/x@sha256:out", _statement())
    assert fake.attested == [("reg/x@sha256:out", _statement())]
    assert ref.predicate_type == "https://houba.dev/predicate/transform/v1"
    assert ref.referrer_digest.startswith("sha256:")


def test_fake_fail_raises_cosign_error() -> None:
    with pytest.raises(CosignError):
        FakeAttestor(fail=True).attest("reg/x@sha256:out", _statement())
