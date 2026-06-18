from __future__ import annotations

import pytest

from houba.config import Settings


def test_scan_evaluator_cmd_defaults_none_and_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOUBA_SCAN_EVALUATOR_CMD", raising=False)
    assert Settings().scan_evaluator_cmd is None
    monkeypatch.setenv("HOUBA_SCAN_EVALUATOR_CMD", "grype sbom:{sbom} -o sarif")
    assert Settings().scan_evaluator_cmd == "grype sbom:{sbom} -o sarif"


def test_scan_evaluator_timeout_defaults_600(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOUBA_SCAN_EVALUATOR_TIMEOUT", raising=False)
    assert Settings().scan_evaluator_timeout == 600


def test_scan_evaluator_timeout_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUBA_SCAN_EVALUATOR_TIMEOUT", "120")
    assert Settings().scan_evaluator_timeout == 120
