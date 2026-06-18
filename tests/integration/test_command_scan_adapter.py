"""Integration tests for CommandScanAdapter (SBOM → SARIF via configured command)."""

from __future__ import annotations

import pytest

from houba.adapters.command_scan import CommandScanAdapter
from houba.errors import ScanEvaluatorError
from houba.ports.sbom import SbomDocument

_DOC = SbomDocument(format="spdx-json", media_type="application/spdx+json", content=b'{"x":1}')


def test_runs_command_and_returns_sarif(fake_bin_path, monkeypatch):
    monkeypatch.setenv("FAKE_GRYPE_SCENARIO", "vulnerable")
    out = CommandScanAdapter("grype sbom:{sbom} -o sarif").evaluate(_DOC)
    assert b'"security-severity":"9.8"' in out.sarif


def test_nonzero_exit_raises(fake_bin_path, monkeypatch):
    monkeypatch.setenv("FAKE_GRYPE_SCENARIO", "fail")
    with pytest.raises(ScanEvaluatorError):
        CommandScanAdapter("grype sbom:{sbom} -o sarif").evaluate(_DOC)


def test_command_without_sbom_placeholder_rejected():
    with pytest.raises(ScanEvaluatorError):
        CommandScanAdapter("grype -o sarif")
