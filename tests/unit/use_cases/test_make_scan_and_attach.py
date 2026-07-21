"""Unit tests for make_scan_and_attach — the SARIF-reading closure factory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from knock.ports.registry import ImageInfo
from knock.use_cases.attach import ScanOutcome
from knock.use_cases.scan_worker import make_scan_and_attach
from tests.fakes.clock import FakeClock
from tests.fakes.registry import FakeRegistryPort

TS = datetime(2026, 6, 26, 10, 0, tzinfo=UTC)
REF = "harbor.example.com/lib/redis@sha256:abc123"

SARIF = json.dumps(
    {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "trivy",
                        "version": "0.50.1",
                        "rules": [],
                    }
                },
                "results": [],
            }
        ],
    }
).encode()


def _registry() -> FakeRegistryPort:
    return FakeRegistryPort(
        infos={REF: ImageInfo(digest="sha256:abc123", created=None, annotations={})}
    )


def _make(sarif_path: str) -> ...:  # type: ignore[return]
    return make_scan_and_attach(
        registry=_registry(),
        clock=FakeClock(TS),
        label_prefix="io.knock",
        sarif_path=sarif_path,
    )


def test_returns_scan_outcome_when_sarif_present(tmp_path: Path) -> None:
    sarif_file = tmp_path / "scan.sarif"
    sarif_file.write_bytes(SARIF)

    fn = _make(str(sarif_file))
    result = fn(REF)

    assert isinstance(result, ScanOutcome)
    assert result.subject_digest == "sha256:abc123"
    assert result.tool == "trivy"


def test_returns_none_when_sarif_missing(tmp_path: Path) -> None:
    fn = _make(str(tmp_path / "missing.sarif"))
    assert fn(REF) is None


def test_returns_none_when_sarif_empty(tmp_path: Path) -> None:
    sarif_file = tmp_path / "empty.sarif"
    sarif_file.write_bytes(b"")

    fn = _make(str(sarif_file))
    assert fn(REF) is None
