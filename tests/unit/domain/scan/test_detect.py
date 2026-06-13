from __future__ import annotations

import json

import pytest

from houba.domain.scan.detect import detect_format, resolve_format
from houba.errors import UnknownFormatError

SARIF = json.dumps({"version": "2.1.0", "runs": []}).encode()


def test_detect_sarif() -> None:
    assert detect_format(SARIF) == "sarif"


def test_detect_returns_none_for_unrecognized_json() -> None:
    assert detect_format(b'{"hello": "world"}') is None


def test_detect_returns_none_for_non_json() -> None:
    assert detect_format(b"not json at all") is None


def test_resolve_uses_detection_when_no_override() -> None:
    assert resolve_format(SARIF, None) == "sarif"


def test_resolve_override_wins() -> None:
    assert resolve_format(b'{"hello":"world"}', "sarif") == "sarif"


def test_resolve_unknown_override_raises() -> None:
    with pytest.raises(UnknownFormatError, match="grype"):
        resolve_format(SARIF, "grype")


def test_resolve_undetectable_without_override_raises() -> None:
    with pytest.raises(UnknownFormatError, match="detect"):
        resolve_format(b"not json", None)
