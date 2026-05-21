"""Fixtures globales pour les tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture()
def fake_bin_path(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Place tests/fake-bins/ en tête de PATH pour ce test."""
    here = Path(__file__).parent / "fake-bins"
    monkeypatch.setenv("PATH", f"{here}{os.pathsep}{os.environ['PATH']}")
    yield here
