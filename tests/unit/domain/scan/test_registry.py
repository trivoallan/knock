from __future__ import annotations

import pytest

from knock.domain.scan.formats.registry import DEFAULT_REGISTRY
from knock.domain.scan.formats.sarif import SarifMapper
from knock.errors import UnknownFormatError


def test_default_registry_has_sarif() -> None:
    assert "sarif" in DEFAULT_REGISTRY.names()
    assert isinstance(DEFAULT_REGISTRY.get("sarif"), SarifMapper)


def test_get_unknown_raises_unknown_format_error() -> None:
    with pytest.raises(UnknownFormatError, match="trivy"):
        DEFAULT_REGISTRY.get("trivy")


def test_mappers_returns_all_registered() -> None:
    assert any(m.name == "sarif" for m in DEFAULT_REGISTRY.mappers())
