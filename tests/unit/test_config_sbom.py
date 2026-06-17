from __future__ import annotations

import pytest
from pydantic import ValidationError

from houba.config import Settings


def test_sbom_formats_default_is_spdx() -> None:
    assert Settings().sbom_formats == ["spdx-json"]


def test_sbom_formats_accepts_both_known_formats() -> None:
    s = Settings(sbom_formats=["spdx-json", "cyclonedx-json"])
    assert s.sbom_formats == ["spdx-json", "cyclonedx-json"]


def test_sbom_formats_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        Settings(sbom_formats=["bogus-format"])


def test_sbom_formats_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        Settings(sbom_formats=[])
