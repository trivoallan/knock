from __future__ import annotations

from houba.adapters.cosign_cli import CosignAdapter
from houba.cli._di import build_container
from houba.config import Settings


def test_no_attestor_when_signer_empty() -> None:
    container = build_container(Settings(attest_signer=""))
    assert container.attestor is None


def test_attestor_wired_when_signer_set() -> None:
    container = build_container(Settings(attest_signer="keyless", attest_builder_id="https://b"))
    assert isinstance(container.attestor, CosignAdapter)
