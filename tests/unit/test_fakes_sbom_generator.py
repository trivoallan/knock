from __future__ import annotations

import pytest

from houba.errors import SyftError
from tests.fakes.sbom_generator import FakeSbomGenerator


def test_fake_returns_one_document_per_format_and_journals() -> None:
    gen = FakeSbomGenerator()
    docs = gen.generate("reg/x@sha256:abc", ["spdx-json", "cyclonedx-json"], tls_verify=False)
    assert [d.format for d in docs] == ["spdx-json", "cyclonedx-json"]
    assert docs[0].media_type == "application/spdx+json"
    assert docs[1].media_type == "application/vnd.cyclonedx+json"
    assert all(d.content for d in docs)
    assert gen.calls == [("reg/x@sha256:abc", ("spdx-json", "cyclonedx-json"), False)]


def test_fake_can_be_configured_to_fail() -> None:
    with pytest.raises(SyftError):
        FakeSbomGenerator(fail=True).generate("reg/x@sha256:abc", ["spdx-json"])
